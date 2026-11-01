"""Small symbolic records used throughout the request pipeline."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class PurposeSeed:
    """A per-request symbolic target, not a learned or numeric latent vector."""

    request: str
    normalized_request: str
    goal: str
    task_type: str
    constraints: tuple[str, ...] = ()
    target_delta: str = "Produce a complete, relevant answer."


@dataclass(frozen=True)
class Action:
    """An abstract skill action inspected by policy before execution."""

    skill: str
    description: str
    arguments: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class GateResult:
    allowed: bool
    reason: str
    rule: str


@dataclass
class Evaluation:
    completion: float
    accuracy: float
    efficiency: float
    overall: float
    checks: list[str] = field(default_factory=list)


@dataclass
class Response:
    text: str
    allowed: bool
    purpose: PurposeSeed
    gate: GateResult
    evaluation: Evaluation | None = None
    action: Action | None = None

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        return result
