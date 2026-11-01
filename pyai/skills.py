"""Deterministic skills and their preflight parsers."""

from __future__ import annotations

import ast
import math
import operator
import re
from dataclasses import dataclass
from typing import Callable

from .models import Action, PurposeSeed


class SkillError(ValueError):
    """A request cannot be safely or unambiguously handled by a skill."""


_BINARY: dict[type[ast.operator], Callable[[float, float], float]] = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}
_UNARY: dict[type[ast.unaryop], Callable[[float], float]] = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
}


def _safe_math(node: ast.AST) -> float:
    if isinstance(node, ast.Expression):
        return _safe_math(node.body)
    if isinstance(node, ast.Constant) and type(node.value) in (int, float):
        if abs(node.value) > 1e100:
            raise SkillError("That number is outside the supported numeric range.")
        return node.value
    if isinstance(node, ast.BinOp) and type(node.op) in _BINARY:
        left, right = _safe_math(node.left), _safe_math(node.right)
        if isinstance(node.op, ast.Pow) and (abs(right) > 12 or abs(left) > 1e100):
            raise SkillError("Exponentiation is limited to keep calculations bounded.")
        value = _BINARY[type(node.op)](left, right)
        if type(value) not in (int, float) or abs(value) > 1e100 or not math.isfinite(value):
            raise SkillError("That calculation is outside the supported real-number range.")
        return value
    if isinstance(node, ast.UnaryOp) and type(node.op) in _UNARY:
        return _UNARY[type(node.op)](_safe_math(node.operand))
    raise SkillError("Only numbers, parentheses, and basic arithmetic operators are supported.")


def parse_expression(text: str) -> str:
    """Extract a numeric expression while accepting ordinary question phrasing."""
    candidate = text.lower().replace(",", "")
    candidate = re.sub(r"\bwhat is\b|\bcalculate\b|\bcompute\b|\bplease\b|\bsolve\b|\bhow much is\b", " ", candidate)
    candidate = candidate.replace("×", "*").replace("÷", "/").replace("^", "**")
    # Word operators are allowed, but avoid attempting arbitrary natural language.
    candidate = re.sub(r"\b(times|multiplied by)\b", "*", candidate)
    candidate = re.sub(r"\b(divided by|over)\b", "/", candidate)
    candidate = re.sub(r"\b(plus|added to)\b", "+", candidate)
    candidate = re.sub(r"\b(minus|less)\b", "-", candidate)
    candidate = candidate.replace("?", " ").strip()
    if not candidate or len(candidate) > 256 or not re.fullmatch(r"[\d.eE+*/()%\-\s]+", candidate):
        raise SkillError("I couldn't isolate a supported arithmetic expression.")
    try:
        parsed = ast.parse(candidate, mode="eval")
        if sum(1 for _ in ast.walk(parsed)) > 64:
            raise SkillError("The expression is too complex for this calculator.")
        _safe_math(parsed)
    except (SyntaxError, ZeroDivisionError, OverflowError, ValueError) as exc:
        if isinstance(exc, SkillError):
            raise
        raise SkillError(f"The expression is not valid: {exc}") from exc
    return candidate


# Factors are expressed relative to the base unit named in each tuple.
_CONVERSIONS: dict[str, tuple[str, str, float]] = {
    "m": ("length", "meter", 1.0), "meter": ("length", "meter", 1.0), "meters": ("length", "meter", 1.0),
    "km": ("length", "meter", 1000.0), "kilometer": ("length", "meter", 1000.0), "kilometers": ("length", "meter", 1000.0),
    "cm": ("length", "meter", 0.01), "centimeter": ("length", "meter", 0.01), "centimeters": ("length", "meter", 0.01),
    "mm": ("length", "meter", 0.001), "mile": ("length", "meter", 1609.344), "miles": ("length", "meter", 1609.344),
    "ft": ("length", "meter", 0.3048), "foot": ("length", "meter", 0.3048), "feet": ("length", "meter", 0.3048),
    "in": ("length", "meter", 0.0254), "inch": ("length", "meter", 0.0254), "inches": ("length", "meter", 0.0254),
    "kg": ("mass", "kilogram", 1.0), "kilogram": ("mass", "kilogram", 1.0), "kilograms": ("mass", "kilogram", 1.0),
    "g": ("mass", "kilogram", 0.001), "gram": ("mass", "kilogram", 0.001), "grams": ("mass", "kilogram", 0.001),
    "lb": ("mass", "kilogram", 0.45359237), "lbs": ("mass", "kilogram", 0.45359237), "pound": ("mass", "kilogram", 0.45359237), "pounds": ("mass", "kilogram", 0.45359237),
    "c": ("temperature", "celsius", 1.0), "celsius": ("temperature", "celsius", 1.0),
    "f": ("temperature", "celsius", 1.0), "fahrenheit": ("temperature", "celsius", 1.0),
}

_CONVERSION_RE = re.compile(
    r"(?:convert\s+)?(-?\d+(?:\.\d+)?)\s*([a-z]+)\s+(?:to|in)\s+([a-z]+)\b", re.I
)


def _convert(value: float, source: str, target: str) -> tuple[float, str]:
    src, dst = source.lower(), target.lower()
    if src not in _CONVERSIONS or dst not in _CONVERSIONS:
        raise SkillError(f"I don't know the unit '{source if src not in _CONVERSIONS else target}'.")
    src_kind, _, src_factor = _CONVERSIONS[src]
    dst_kind, _, dst_factor = _CONVERSIONS[dst]
    if src_kind != dst_kind:
        raise SkillError("Those units measure different things, so they cannot be converted.")
    if src_kind == "temperature":
        celsius = (value - 32) * 5 / 9 if src in ("f", "fahrenheit") else value
        result = celsius * 9 / 5 + 32 if dst in ("f", "fahrenheit") else celsius
    else:
        result = value * src_factor / dst_factor
    return result, dst


def _format_number(value: float) -> str:
    if value == int(value):
        return str(int(value))
    return f"{value:.8g}"


def infer_action(seed: PurposeSeed) -> Action:
    text = seed.normalized_request
    if seed.task_type == "arithmetic":
        expression = parse_expression(text)
        return Action("arithmetic", "Evaluate a bounded arithmetic expression", {"expression": expression})
    if seed.task_type == "conversion":
        match = _CONVERSION_RE.search(text)
        if not match:
            raise SkillError("Use a form such as 'convert 5 km to miles'.")
        value, source, target = match.groups()
        # Validate units and dimensions during preflight, before execution.
        _convert(float(value), source, target)
        return Action("conversion", "Convert between compatible known units", {"value": float(value), "source": source, "target": target})
    if seed.task_type == "planning":
        objective = re.sub(r"^(please\s+)?(make|create|give me|write)\s+(a\s+)?(simple\s+)?(plan|steps)\s+(to|for)\s+", "", text).strip(" .?!")
        if not objective:
            objective = text.strip(" .?!")
        return Action("planning", "Create a generic, reversible checklist for the stated goal", {"objective": objective})
    return Action("help", "Explain supported deterministic capabilities", {})


def execute(action: Action) -> tuple[str, list[str]]:
    """Run one already-authorized action and return its response and verification checks."""
    if action.skill == "arithmetic":
        expression = action.arguments["expression"]
        value = _safe_math(ast.parse(expression, mode="eval"))
        return f"{expression} = {_format_number(value)}", ["expression parsed with the restricted arithmetic grammar", "result is finite and within the configured range"]
    if action.skill == "conversion":
        value, source, target = action.arguments["value"], action.arguments["source"], action.arguments["target"]
        result, target = _convert(value, source, target)
        return f"{_format_number(value)} {source} = {_format_number(result)} {target}", ["source and target units are known", "units have compatible dimensions"]
    if action.skill == "planning":
        objective = action.arguments["objective"]
        steps = [
            f"Define what 'done' means for {objective} and note any constraints.",
            "Break the work into small, reversible actions.",
            "Complete the highest-priority first action and record the result.",
            "Review progress; adjust the next action based on what changed.",
        ]
        return "A simple plan:\n" + "\n".join(f"{i}. {step}" for i, step in enumerate(steps, 1)), ["plan contains an explicit goal", "steps are ordered and actionable"]
    return (
        "I use explicit rules rather than a language model. I can calculate basic arithmetic, "
        "convert common metric/imperial units, or draft a simple checklist. Rephrase your request "
        "as one of those tasks and I can try it.",
        ["capabilities stated without inventing an answer"],
    )
