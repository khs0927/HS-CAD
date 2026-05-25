"""
Standalone review-only CLI for HS-CAD overlay v4.

Use this before patching ``src.main``:

    python -X utf8 -m hscad.app.cli_review_only main-code --input ... --out ...
    python -X utf8 -m hscad.app.cli_review_only evidence-bridge --legacy-dir ... --out ...
"""

from __future__ import annotations

from pathlib import Path
import argparse
from .review_cli_registry import (
    run_evidence_bridge_review_pipeline,
    run_main_code_review_pipeline,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="HS-CAD review-only overlay commands")
    sub = parser.add_subparsers(dest="command", required=True)

    main_code = sub.add_parser("main-code", help="Run main-code review pipeline")
    main_code.add_argument("--input", required=True, type=Path)
    main_code.add_argument("--out", required=True, type=Path)

    bridge = sub.add_parser("evidence-bridge", help="Run legacy artifact evidence bridge")
    bridge.add_argument("--legacy-dir", required=True, type=Path)
    bridge.add_argument("--out", required=True, type=Path)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "main-code":
        result = run_main_code_review_pipeline(args.input, args.out)
    elif args.command == "evidence-bridge":
        result = run_evidence_bridge_review_pipeline(args.legacy_dir, args.out)
    else:  # pragma: no cover
        raise SystemExit(f"Unknown command: {args.command}")
    print(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
