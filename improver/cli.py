"""`improve` subcommand glue, kept out of the top-level cli.py for cohesion.

Reads a prompt either inline (positional) or from ``--file``, runs the improver,
and renders the result. With ``--plain`` it prints just the rewritten prompt to
stdout (useful for piping into a new ``.prompt.md``).
"""

from __future__ import annotations

from pathlib import Path

from improver.improve import improve
from improver.render import render


def add_parser(subparsers) -> None:
    p = subparsers.add_parser("improve", help="diagnose & rewrite a weak prompt")
    src = p.add_mutually_exclusive_group(required=True)
    src.add_argument("prompt", nargs="?", help="the raw prompt text to improve")
    src.add_argument("--file", type=Path, help="read the raw prompt from a file")
    p.add_argument(
        "--rule-based",
        action="store_true",
        help="force the deterministic rewriter even if a key is set",
    )
    p.add_argument(
        "--plain",
        action="store_true",
        help="print only the rewritten prompt to stdout (no diagnosis/UI)",
    )
    p.set_defaults(func=cmd_improve)


def cmd_improve(args) -> int:
    if args.file:
        if not args.file.exists():
            print(f"File not found: {args.file}")
            return 1
        raw = args.file.read_text(encoding="utf-8")
    else:
        raw = args.prompt or ""

    if not raw.strip():
        print("Nothing to improve: the prompt is empty.")
        return 1

    result = improve(raw, force_rule_based=args.rule_based)

    if args.plain:
        print(result.improved)
        return 0

    render(result)
    return 0
