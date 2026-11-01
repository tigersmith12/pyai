"""Command-line interface for the symbolic assistant."""

from __future__ import annotations

import argparse
import json

from .core import Assistant


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Purely logic-based, deterministic Python assistant")
    parser.add_argument("request", nargs="*", help="request to process; omit to start interactive mode")
    parser.add_argument("--context", default="", help="optional constraints or context for this request")
    parser.add_argument("--json", action="store_true", help="include purpose, gate, and operational evaluation")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    assistant = Assistant()
    if args.request:
        response = assistant.respond(" ".join(args.request), context=args.context)
        print(json.dumps(response.to_dict(), indent=2, ensure_ascii=False) if args.json else response.text)
        return 0 if response.allowed else 2

    print("pyai — deterministic logic assistant (type 'quit' to exit)")
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
        response = assistant.respond(request, context=args.context)
        print("pyai> " + response.text)
