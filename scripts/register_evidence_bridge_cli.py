"""Patch src/main.py to register the review-only evidence bridge Typer command.

The script supports dry-run and refuses to patch if it cannot find a safe Typer
app pattern. It does not register CAD execution or live runner commands.
"""
from __future__ import annotations

import argparse
import difflib
from pathlib import Path

IMPORT_LINE = "from hscad.app.src_main_bridge_v3 import register_evidence_bridge_command\n"
REGISTER_LINE = "register_evidence_bridge_command(app)\n"
OPTIONAL_IMPORT = "from hscad.app.src_main_bridge_v3 import register_evidence_bridge_command as _register_hscad_evidence_bridge_command\n"
OPTIONAL_BLOCK = "if _register_hscad_evidence_bridge_command is not None:\n    _register_hscad_evidence_bridge_command(app)\n"


def build_patch(text: str) -> str:
    if IMPORT_LINE in text and REGISTER_LINE in text:
        return text
    if "_register_hscad_evidence_bridge_command" in text or "register_evidence_bridge_command(app)" in text:
        return text
    if "from src.app.cli import app" in text:
        lines = text.splitlines(keepends=True)
        insert_at = 0
        for i, line in enumerate(lines):
            if line.startswith("from __future__ import "):
                insert_at = i + 1
        lines.insert(insert_at, "\n# HS-CAD evidence bridge: review-only hscad-evidence-bridge command.\ntry:\n")
        lines.insert(insert_at + 1, f"    {OPTIONAL_IMPORT}")
        lines.insert(insert_at + 2, "except Exception:  # pragma: no cover - keeps legacy CLI importable if overlay is absent\n")
        lines.insert(insert_at + 3, "    _register_hscad_evidence_bridge_command = None\n\n")
        text = "".join(lines)
        if "__name__ == '__main__'" in text:
            marker = "\nif __name__ == '__main__':"
        elif '__name__ == "__main__"' in text:
            marker = '\nif __name__ == "__main__":'
        else:
            raise RuntimeError("Could not find Typer app entrypoint in src/main.py")
        return text.replace(marker, "\n" + OPTIONAL_BLOCK + marker, 1)
    lines = text.splitlines(keepends=True)
    if IMPORT_LINE not in text:
        insert_at = 0
        for i, line in enumerate(lines):
            if line.startswith("import ") or line.startswith("from "):
                insert_at = i + 1
        lines.insert(insert_at, IMPORT_LINE)
    text = "".join(lines)
    if REGISTER_LINE not in text:
        marker = "app = typer.Typer"
        idx = text.find(marker)
        if idx == -1:
            marker = "typer.Typer("
            idx = text.find(marker)
        if idx == -1:
            raise RuntimeError("Could not find Typer app declaration in src/main.py")
        line_end = text.find("\n", idx)
        if line_end == -1:
            line_end = len(text)
        text = text[: line_end + 1] + REGISTER_LINE + text[line_end + 1 :]
    return text


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", required=True)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    main_py = Path(args.repo_root) / "src" / "main.py"
    old = main_py.read_text(encoding="utf-8")
    new = build_patch(old)
    if old == new:
        print("NO_CHANGE src/main.py already contains evidence bridge registration")
        return 0
    diff = "".join(difflib.unified_diff(old.splitlines(keepends=True), new.splitlines(keepends=True), fromfile="src/main.py", tofile="src/main.py"))
    print(diff)
    if args.dry_run:
        print("DRY_RUN only")
        return 0
    main_py.write_text(new, encoding="utf-8")
    print("PATCHED src/main.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
