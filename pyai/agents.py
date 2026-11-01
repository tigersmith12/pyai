"""Bounded multi-agent orchestration, initially backed by simulated agents.

Agents return proposals only. The manager gates the request and every result;
it never gives an agent direct access to execute PyAI skills or arbitrary tools.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Protocol

from .intent import build_purpose_seed
from .models import Action, GateResult, PurposeSeed
from .policy import SafetyPolicy


@dataclass(frozen=True)
class AgentTask:
    """A role-specific task anchored to the shared, immutable request purpose."""

    role: str
    objective: str
    purpose: PurposeSeed
    request: str
    context: str = ""
    prior_results: tuple["AgentResult", ...] = ()


@dataclass(frozen=True)
class AgentResult:
    """Untrusted text proposed by an agent."""

    role: str
    content: str


class Agent(Protocol):
    """Interface future fake or hosted-model agents must implement."""

    role: str

    def run(self, task: AgentTask) -> AgentResult:
        """Return a proposal for the assigned task."""
        ...


@dataclass(frozen=True)
class AgentRun:
    """Auditable result of one bounded manager workflow."""

    text: str
    allowed: bool
    completed: bool
    gate: GateResult
    purpose: PurposeSeed
    agent_calls: int
    results: tuple[AgentResult, ...] = ()
    stopped_at: str | None = None

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


class AgentManager:
    """Runs a fixed planner -> critic -> synthesizer pipeline."""

    ROLES = ("planner", "critic", "synthesizer")

    def __init__(
        self,
        planner: Agent,
        critic: Agent,
        synthesizer: Agent,
        *,
        policy: SafetyPolicy | None = None,
        max_calls: int = 3,
    ) -> None:
        if not 1 <= max_calls <= len(self.ROLES):
            raise ValueError(f"max_calls must be between 1 and {len(self.ROLES)}")
        supplied = (planner, critic, synthesizer)
        for expected, agent in zip(self.ROLES, supplied):
            if agent.role != expected:
                raise ValueError(f"Expected a {expected!r} agent, got {agent.role!r}")
        self._agents = dict(zip(self.ROLES, supplied))
        self.policy = policy or SafetyPolicy()
        self.max_calls = max_calls

    def run(self, request: str, context: str = "") -> AgentRun:
        """Seed intent, gate it, then anchor every role to the same purpose record."""
        purpose = build_purpose_seed(request, context, task_type="planning")
        purpose_context = "\n".join((
            f"Purpose goal: {purpose.goal}",
            f"Success criteria: {'; '.join(purpose.success_criteria)}",
            f"Constraints: {'; '.join(purpose.constraints) or 'none stated'}",
            f"Non-goals: {'; '.join(purpose.non_goals)}",
            f"Exploration guidance: {purpose.exploration_guidance}",
        ))
        gate_context = f"{context}\n{purpose_context}".strip()
        preview = Action(
            skill="multi_agent_plan",
            description=f"Draft, review, and synthesize a plan for this purpose: {purpose.goal}",
        )
        gate = self.policy.evaluate(request, gate_context, preview)
        if not gate.allowed:
            return AgentRun(
                text=gate.reason,
                allowed=False,
                completed=False,
                gate=gate,
                purpose=purpose,
                agent_calls=0,
            )

        criteria = "; ".join(purpose.success_criteria)
        constraints = "; ".join(purpose.constraints) or "No additional user constraints were stated."
        objectives = {
            "planner": (
                f"Draft a short, ordered plan for the purpose goal: {purpose.goal}. "
                f"Target: {purpose.target_delta} Success criteria: {criteria} "
                f"Constraints: {constraints} Non-goals: {'; '.join(purpose.non_goals)} "
                f"Exploration guidance: {purpose.exploration_guidance}"
            ),
            "critic": (
                f"Compare the planner's draft with this same purpose seed: goal={purpose.goal}; "
                f"success criteria={criteria}; constraints={constraints}; "
                f"exploration guidance={purpose.exploration_guidance}. Identify any material gap, "
                "unsupported assumption, or irrelevant tangent."
            ),
            "synthesizer": (
                f"Synthesize a final response anchored to the same purpose goal={purpose.goal}; target={purpose.target_delta}; "
                f"success criteria={criteria}; constraints={constraints}; "
                f"non-goals={' ; '.join(purpose.non_goals)}; "
                f"exploration guidance={purpose.exploration_guidance}. Consider the draft and critique."
            ),
        }
        results: list[AgentResult] = []
        calls = 0
        for role in self.ROLES:
            if calls >= self.max_calls:
                return AgentRun(
                    text=f"The workflow stopped at its {self.max_calls}-call limit before synthesis; no final answer was produced.",
                    allowed=True,
                    completed=False,
                    gate=gate,
                    purpose=purpose,
                    agent_calls=calls,
                    results=tuple(results),
                    stopped_at=role,
                )

            task = AgentTask(
                role=role,
                objective=objectives[role],
                purpose=purpose,
                request=request,
                context=context,
                prior_results=tuple(results),
            )
            calls += 1
            agent = self._agents[role]
            try:
                result = agent.run(task)
            except Exception as exc:
                return AgentRun(
                    text=f"The {role} agent failed ({type(exc).__name__}); no final answer was produced.",
                    allowed=True,
                    completed=False,
                    gate=gate,
                    purpose=purpose,
                    agent_calls=calls,
                    results=tuple(results),
                    stopped_at=role,
                )

            if not isinstance(result, AgentResult) or result.role != role or not isinstance(result.content, str) or not result.content.strip():
                return AgentRun(
                    text=f"The {role} agent returned an invalid result; no final answer was produced.",
                    allowed=True,
                    completed=False,
                    gate=gate,
                    purpose=purpose,
                    agent_calls=calls,
                    results=tuple(results),
                    stopped_at=role,
                )

            output_gate = self.policy.evaluate(
                request,
                gate_context,
                Action(skill="agent_output", description=result.content),
            )
            if not output_gate.allowed:
                # Do not return or forward the rejected proposal or any partial answer.
                return AgentRun(
                    text=output_gate.reason,
                    allowed=False,
                    completed=False,
                    gate=output_gate,
                    purpose=purpose,
                    agent_calls=calls,
                    stopped_at=role,
                )
            results.append(result)

        final_text = results[-1].content
        return AgentRun(
            text=final_text,
            allowed=True,
            completed=True,
            gate=gate,
            purpose=purpose,
            agent_calls=calls,
            results=tuple(results),
        )


class SimulatedPlanner:
    """Deterministic stand-in used to test orchestration without a live model."""

    role = "planner"

    def run(self, task: AgentTask) -> AgentResult:
        content = (
            f"Plan for: {task.request.strip()}\n"
            "1. Define what 'done' looks like and note any constraints.\n"
            "2. Break the work into small, reversible actions.\n"
            "3. Complete the highest-priority action and record the result.\n"
            "4. Review progress and adjust the next step."
        )
        return AgentResult(role=self.role, content=content)


class SimulatedCritic:
    """A deterministic reviewer that identifies one useful completion criterion."""

    role = "critic"

    def run(self, task: AgentTask) -> AgentResult:
        if not task.prior_results:
            return AgentResult(role=self.role, content="The draft is missing; ask the planner to try again.")
        draft = task.prior_results[0].content.lower()
        needs_completion_check = any(
            "complete" in criterion.lower() or "completion" in criterion.lower()
            for criterion in task.purpose.success_criteria
        )
        if needs_completion_check and "stop when" not in draft:
            content = "Review: against the purpose's completion criterion, add a clear stopping condition."
        else:
            content = "Review: the draft appears to address the purpose's stated success criteria."
        return AgentResult(role=self.role, content=content)


class SimulatedSynthesizer:
    """Combines the simulated draft and review into one user-facing plan."""

    role = "synthesizer"

    def run(self, task: AgentTask) -> AgentResult:
        if len(task.prior_results) != 2:
            return AgentResult(role=self.role, content="Cannot synthesize without both a draft and a review.")
        draft, review = task.prior_results
        content = draft.content
        needs_completion_check = any(
            "complete" in criterion.lower() or "completion" in criterion.lower()
            for criterion in task.purpose.success_criteria
        )
        if needs_completion_check and "stopping condition" in review.content.lower():
            content += "\n5. Stop when the goal's completion condition is met."
        return AgentResult(role=self.role, content=content)


def simulated_manager(*, policy: SafetyPolicy | None = None, max_calls: int = 3) -> AgentManager:
    """Construct the built-in no-model workflow."""
    return AgentManager(
        SimulatedPlanner(),
        SimulatedCritic(),
        SimulatedSynthesizer(),
        policy=policy,
        max_calls=max_calls,
    )
