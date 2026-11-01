"""Explicit, conservative safety rules for the pre-execution gate."""

from __future__ import annotations

import re

from .models import Action, GateResult


# These are intentionally explicit rule lists, not a general-purpose moral model.
# Match an actionable combination rather than isolated words such as "weapon".
_DENY_RULES: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("self_harm", re.compile(r"\b(?:instructions?|steps?|method|ways?)\s+(?:to\s+)?(?:kill|harm|injure)\s+myself\b|\bhow\s+(?:can|do)\s+i\s+(?:kill|hurt|harm)\s+myself\b", re.I)),
    ("violent_harm", re.compile(r"\b(?:how\s+to\s+)?(?:kill|murder|poison|attack|injure|hurt)\s+(?:someone|somebody|a person|people|myself|yourself|him|her|them)\b", re.I)),
    ("weapon_construction", re.compile(r"\b(?:build|make|construct|assemble|instructions?\s+for)\b.{0,50}\b(?:bomb|explosive|firearm|weapon)\b", re.I)),
    ("cyber_abuse", re.compile(r"\b(?:write|create|deploy|make|use|build)\b.{0,55}\b(?:malware|ransomware|keylogger|credential stealer|virus)\b|\b(?:steal|phish|harvest)\b.{0,45}\b(?:passwords?|credentials?|logins?)\b|\b(?:break into|hack)\b.{0,40}\b(?:someone else's|another person's|a stranger's)\s+(?:account|computer|network)\b", re.I)),
    ("evasion", re.compile(r"\b(?:evade|bypass|disable)\b.{0,45}\b(?:law enforcement|police|security alarm|access control|security controls)\b", re.I)),
)


class SafetyPolicy:
    """Deterministic deny-list gate; unknown requests are not treated as endorsed."""

    def evaluate(self, request: str, context: str, action: Action) -> GateResult:
        inspected = f"{request}\n{context}\n{action.description}"
        for rule, pattern in _DENY_RULES:
            if pattern.search(inspected):
                return GateResult(
                    allowed=False,
                    rule=rule,
                    reason=("This request appears to seek actionable help for harm or abuse. "
                            "The task was stopped before its skill executed."),
                )
        return GateResult(
            allowed=True,
            rule="no_explicit_deny_rule_matched",
            reason="No configured deny rule matched; this is a limited rule check, not a guarantee of safety.",
        )
