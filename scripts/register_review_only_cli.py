#!/usr/bin/env python
"""Patch ``src/main.py`` to register review-only HS-CAD commands.

Default behavior is dry-run. Pass ``--apply`` to write changes.

The patch is intentionally small:
1. Add an import for ``register_review_only_commands``.
2. Add ``register_review_only_commands(app)`` after the Typer app is created.

It refuses to patch files that do not appear to use a Typer ``app`` object.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import argparse
import difflib
import re
import sys


IMPORT_LINE = "from hscad.app.review_cli_registry import register_review_only_commands"
CALL_LINE = "register_review_only_commands(app)"


@dataclass(frozen=True)
class PatchResult:
    changed: bool
    reason: str
    before: str
    after: str


def _find_app_insertion_point(text: str) -> int | None:
    """Return line index after a Typer app creation line."""

    lines = text.splitlines()
    patterns = (
        re.compile(r"^\s*app\s*=\s*typer\.Typer\s*\("),
        re.compile(r"^\s*app\s*=\s*Typer\s*\("),
    )
    for idx, line in enumerate(lines):
        if any(p.search(line) for p in patterns):
            # Insert after the full statement. Most projects keep this one-line,
            # but allow a simple multi-line Typer(...) block.
            depth = line.count("(") - line.count(")")
            end_idx = idx
            while depth > 0 and end_idx + 1 < len(lines):
                end_idx += 1
                depth += lines[end_idx].count("(") - lines[end_idx].count(")")
            return end_idx + 1
    return None


def patch_src_main(text: str) -> PatchResult:
    before = text
    if CALL_LINE in text and IMPORT_LINE in text:
        return PatchResult(False, "already_registered", before, before)

    lines = text.splitlines()
    changed = False

    if "from src.app.cli import app" in text:
        optional_import = (
            "try:\n"
            "    from hscad.app.review_cli_registry import register_review_only_commands as _register_hscad_review_only_commands\n"
            "except Exception:  # pragma: no cover - keeps legacy CLI importable if overlay is absent\n"
            "    _register_hscad_review_only_commands = None"
        )
        optional_call = (
            "if _register_hscad_review_only_commands is not None:\n"
            "    _register_hscad_review_only_commands(app)"
        )
        if "_register_hscad_review_only_commands" in text:
            return PatchResult(False, "already_registered", before, before)
        insert_at = 0
        for idx, line in enumerate(lines):
            if line.startswith("from __future__ import "):
                insert_at = idx + 1
        lines.insert(insert_at, "")
        lines.insert(insert_at + 1, "# HS-CAD review-only overlay commands.")
        lines.insert(insert_at + 2, optional_import)
        text = "\n".join(lines) + ("\n" if before.endswith("\n") else "")
        if "__name__ == '__main__'" in text:
            marker = "\nif __name__ == '__main__':"
        elif '__name__ == "__main__"' in text:
            marker = '\nif __name__ == "__main__":'
        else:
            return PatchResult(
                False,
                "typer_app_not_found_refusing_to_patch",
                before,
                before,
            )
        after = text.replace(marker, "\n" + optional_call + "\n" + marker, 1)
        return PatchResult(True, "patched", before, after)

    if IMPORT_LINE not in text:
        # Put our import after the last import/from line near the top.
        insert_at = 0
        for idx, line in enumerate(lines[:80]):
            if line.startswith("import ") or line.startswith("from "):
                insert_at = idx + 1
        lines.insert(insert_at, IMPORT_LINE)
        changed = True

    text = "\n".join(lines) + ("\n" if before.endswith("\n") else "")
    lines = text.splitlines()

    if CALL_LINE not in text:
        insertion = _find_app_insertion_point(text)
        if insertion is None:
            return PatchResult(
                False,
                "typer_app_not_found_refusing_to_patch",
                before,
                before,
            )
        lines.insert(insertion, CALL_LINE)
        changed = True

    after = "\n".join(lines) + ("\n" if before.endswith("\n") else "")
    return PatchResult(changed, "patched" if changed else "unchanged", before, after)


def unified_diff(before: str, after: str, path: Path) -> str:
    return "\n".join(
        difflib.unified_diff(
            before.splitlines(),
            after.splitlines(),
            fromfile=f"{path} (before)",
            tofile=f"{path} (after)",
            lineterm="",
        )
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument("--apply", action="store_true", help="Actually patch src/main.py")
    parser.add_argument("--dry-run", action="store_true", help="Show patch only; default")
    args = parser.parse_args(argv)

    repo_root = args.repo_root.resolve()
    target = repo_root / "src" / "main.py"
    if not target.exists():
        print(f"[ERROR] src/main.py not found: {target}", file=sys.stderr)
        return 2

    text = target.read_text(encoding="utf-8")
    result = patch_src_main(text)
    print(f"[register_review_only_cli] {result.reason}")

    if result.before != result.after:
        print(unified_diff(result.before, result.after, target))

    if args.apply:
        if result.reason == "typer_app_not_found_refusing_to_patch":
            print("[ERROR] Refusing to patch: Typer app object not found", file=sys.stderr)
            return 3
        target.write_text(result.after, encoding="utf-8")
        print(f"[register_review_only_cli] wrote {target}")
    else:
        print("[register_review_only_cli] dry-run only; pass --apply to write")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
