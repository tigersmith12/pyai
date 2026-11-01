"""Four-phase symbolic request pipeline."""

from __future__ import annotations

import re

from .models import Action, Evaluation, PurposeSeed, Response
from .policy import SafetyPolicy
from .skills import SkillError, execute, infer_action


class Assistant:
    """A small deterministic assistant whose behavior is inspectable and testable."""

    def __init__(self, policy: SafetyPolicy | None = None) -> None:
        self.policy = policy or SafetyPolicy()

    @staticmethod
    def _make_seed(request: str, context: str) -> PurposeSeed:
        normalized = " ".join(request.lower().split())
        if re.search(r"\b(convert|conversion)\b|\b\d+(?:\.\d+)?\s*[a-z]+\s+(?:to|in)\s+[a-z]+\b", normalized):
            task_type, goal = "conversion", "convert the given quantity"
        elif re.search(r"\b(plan|checklist|steps)\b", normalized):
            task_type, goal = "planning", "create an ordered plan for the stated objective"
        elif re.search(r"\d.*(?:[+*/%]|\-\s*\d|\b(?:plus|minus|times|divided by)\b)", normalized):
            task_type, goal = "arithmetic", "evaluate the requested arithmetic"
        else:
            task_type, goal = "unsupported", "respond honestly within supported capabilities"

        constraints: list[str] = []
        combined = f"{request} {context}".lower()
        if re.search(r"\b(brief|briefly|concise|short answer)\b", combined):
            constraints.append("be concise")
        if re.search(r"\b(step by step|show steps|explain the steps)\b", combined):
            constraints.append("show a concise method")
        if context.strip():
            constraints.append("respect the supplied context")
        delta = {
            "arithmetic": "Resolve the expression to one checked numeric result.",
            "conversion": "Return the equivalent quantity in the requested compatible unit.",
            "planning": "Turn the stated goal into a short ordered checklist.",
            "unsupported": "State capability limits without fabricating an answer.",
        }[task_type]
        return PurposeSeed(
            request=request,
            normalized_request=normalized,
            goal=goal,
            task_type=task_type,
            constraints=tuple(constraints),
            target_delta=delta,
        )

    def respond(self, request: str, context: str = "") -> Response:
        """Synthesize purpose, gate a simulated action, execute, then score the result."""
        seed = self._make_seed(request, context)
        # Simulation is a bounded description of the intended skill, not execution.
        previews = {
            "arithmetic": Action("arithmetic", "Evaluate the user's arithmetic expression"),
            "conversion": Action("conversion", "Convert the user's quantity between units"),
            "planning": Action("planning", "Draft a simple plan for the user's stated goal"),
            "unsupported": Action("help", "Explain supported capabilities without inventing an answer"),
        }
        preview = previews[seed.task_type]
        gate = self.policy.evaluate(request, context, preview)
        if not gate.allowed:
            return Response(
                text=gate.reason,
                allowed=False,
                purpose=seed,
                gate=gate,
            )

        try:
            action = infer_action(seed)
            text, checks = execute(action)
        except SkillError as exc:
            # This is a deterministic input-validation failure, not partial skill output.
            action = preview
            text = f"I couldn't complete that request: {exc}"
            checks = ["request did not satisfy the selected skill's input requirements"]

        completion = 1.0 if not text.startswith("I couldn't complete") else 0.0
        accuracy = 1.0 if checks and all(checks) else 0.0
        efficiency = 1.0 if action.skill != "help" else 0.9
        evaluation = Evaluation(
            completion=completion,
            accuracy=accuracy,
            efficiency=efficiency,
            overall=round(0.4 * completion + 0.4 * accuracy + 0.2 * efficiency, 3),
            checks=checks,
        )
        return Response(text=text, allowed=True, purpose=seed, gate=gate, evaluation=evaluation, action=action)
