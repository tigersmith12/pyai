"""Build an explicit, immutable purpose seed for one request."""

from __future__ import annotations

import re

from .models import PurposeSeed


_TASK_DETAILS = {
    "arithmetic": (
        "evaluate the requested arithmetic",
        "Resolve the expression to one checked numeric result.",
        ("Return the result of the parsed expression.", "Keep the result finite and within the supported range."),
    ),
    "conversion": (
        "convert the given quantity",
        "Return the equivalent quantity in the requested compatible unit.",
        ("Use compatible source and target units.", "Return the converted quantity in the target unit."),
    ),
    "planning": (
        "create an ordered plan for the stated objective",
        "Turn the stated goal into a short ordered checklist.",
        (
            "Keep the plan relevant to the stated goal.",
            "Provide ordered, actionable steps that respect the stated constraints.",
            "Include a clear way to tell when the goal is complete.",
        ),
    ),
    "unsupported": (
        "respond honestly within supported capabilities",
        "State capability limits without fabricating an answer.",
        ("Be transparent about unsupported requests.", "Do not invent facts or claim work was performed."),
    ),
}


def build_purpose_seed(
    request: str,
    context: str = "",
    *,
    task_type: str | None = None,
) -> PurposeSeed:
    """Create a one-request symbolic intent seed; no model or embeddings are used."""
    normalized = " ".join(request.lower().split())
    if task_type is None:
        if re.search(r"\b(convert|conversion)\b|\b\d+(?:\.\d+)?\s*[a-z]+\s+(?:to|in)\s+[a-z]+\b", normalized):
            task_type = "conversion"
        elif re.search(r"\b(plan|checklist|steps)\b", normalized):
            task_type = "planning"
        elif re.search(r"\d.*(?:[+*/%]|\-\s*\d|\b(?:plus|minus|times|divided by)\b)", normalized):
            task_type = "arithmetic"
        else:
            task_type = "unsupported"
    if task_type not in _TASK_DETAILS:
        raise ValueError(f"Unknown task type for purpose seed: {task_type}")

    goal, target_delta, success_criteria = _TASK_DETAILS[task_type]
    if task_type == "planning":
        goal = f"Create a useful plan for the user's stated goal: {request.strip()}"
    constraints: list[str] = []
    combined = f"{request} {context}".lower()
    if re.search(r"\b(brief|briefly|concise|short answer)\b", combined):
        constraints.append("be concise")
    if re.search(r"\b(step by step|show steps|explain the steps)\b", combined):
        constraints.append("show a concise method")
    if context.strip():
        constraints.append("respect the supplied context")

    return PurposeSeed(
        request=request,
        normalized_request=normalized,
        goal=goal,
        task_type=task_type,
        constraints=tuple(constraints),
        target_delta=target_delta,
        success_criteria=success_criteria,
        non_goals=("Do not pursue unrelated tangents.", "Do not present assumptions or speculation as established fact."),
    )
