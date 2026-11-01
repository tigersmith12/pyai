"""Command-line interface for the symbolic assistant."""

from __future__ import annotations

import argparse
import json

from .agents import AgentRun, simulated_manager
from .core import Assistant
from .models import Response


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="PyAI: deterministic skills with an optional simulated-agent demo")
    parser.add_argument("request", nargs="*", help="request to process; omit to start interactive mode")
    parser.add_argument("--context", default="", help="optional constraints or context for this request")
    parser.add_argument("--mode", choices=("logic", "simulated-agents"), default="logic", help="logic-only mode (default) or the no-model planner/critic/synthesizer demo")
    parser.add_argument("--json", action="store_true", help="include purpose or agent workflow diagnostics")
    return parser


def _respond(assistant: Assistant, mode: str, request: str, context: str) -> Response | AgentRun:
    if mode == "simulated-agents":
        return simulated_manager().run(request, context)
    return assistant.respond(request, context=context)


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    assistant = Assistant()
    if args.request:
        response = _respond(assistant, args.mode, " ".join(args.request), args.context)
        print(json.dumps(response.to_dict(), indent=2, ensure_ascii=False) if args.json else response.text)
        completed = response.completed if isinstance(response, AgentRun) else True
        return 0 if response.allowed and completed else 2

    print(f"pyai — {args.mode} mode (type 'quit' to exit)")
    while True:
        try:
            request = input("you> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return 0
        if request.lower() in {"quit", "exit"}:
            return 0
        if not request:
            continue
        response = _respond(assistant, args.mode, request, args.context)
        if args.json:
            print(json.dumps(response.to_dict(), indent=2, ensure_ascii=False))
        else:
            print("pyai> " + response.text)
