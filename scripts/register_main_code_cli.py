"""Safely register the review-only main-code command in src/main.py."""
from __future__ import annotations

import argparse
import difflib
import re
from pathlib import Path

MARKER = "HS-CAD main-code overlay bridge"
IMPORT_SNIPPET = "\n# HS-CAD main-code overlay bridge: review-only hscad-main-code-pipeline dispatch.\ntry:\n    from hscad.app.src_main_bridge import dispatch_if_main_code_command as _hscad_main_code_dispatch\nexcept Exception:  # pragma: no cover - keeps legacy CLI importable if overlay is absent\n    _hscad_main_code_dispatch = None\n\n"
BODY_SNIPPET = "\n    if _hscad_main_code_dispatch is not None:\n        _hscad_main_code_result = _hscad_main_code_dispatch()\n        if _hscad_main_code_result is not None:\n            return _hscad_main_code_result\n"
TYPER_IMPORT_SNIPPET = "\n# HS-CAD main-code overlay bridge: review-only hscad-main-code-pipeline command.\ntry:\n    from hscad.app.src_main_bridge import register_main_code_command as _register_hscad_main_code_command\nexcept Exception:  # pragma: no cover - keeps legacy CLI importable if overlay is absent\n    _register_hscad_main_code_command = None\n\n"
TYPER_REGISTER_SNIPPET = "\nif _register_hscad_main_code_command is not None:\n    _register_hscad_main_code_command(app)\n\n"


def patch_text(text: str) -> tuple[str, str]:
    if MARKER in text:
        return text, "already_patched"
    if "from src.app.cli import app" in text:
        future_matches = list(re.finditer(r"^from __future__ import [^\n]+\n", text, flags=re.MULTILINE))
        import_at = future_matches[-1].end() if future_matches else 0
        patched = text[:import_at] + TYPER_IMPORT_SNIPPET + text[import_at:]
        if "__name__ == '__main__'" in patched:
            marker = "\nif __name__ == '__main__':"
        elif '__name__ == "__main__"' in patched:
            marker = '\nif __name__ == "__main__":'
        else:
            marker = ""
        if not marker:
            return text, "no_typer_entrypoint_found"
        patched = patched.replace(marker, TYPER_REGISTER_SNIPPET + marker, 1)
        return patched, "patched"
    match = re.search(r"^def\s+main\s*\([^\n]*\)\s*(?:->\s*[^:]+)?\s*:\s*$", text, flags=re.MULTILINE)
    if not match:
        return text, "no_def_main_found"
    insert_at = match.end()
    patched = text[:insert_at] + BODY_SNIPPET + text[insert_at:]
    future_matches = list(re.finditer(r"^from __future__ import [^\n]+\n", patched, flags=re.MULTILINE))
    import_at = future_matches[-1].end() if future_matches else 0
    patched = patched[:import_at] + IMPORT_SNIPPET + patched[import_at:]
    return patched, "patched"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    target = Path(args.repo_root) / "src" / "main.py"
    if not target.exists():
        print(f"SKIP: {target} not found")
        return 2
    original = target.read_text(encoding="utf-8")
    patched, status = patch_text(original)
    print(f"STATUS={status}")
    print("TARGET=src/main.py")
    if status != "patched":
        return 0 if status == "already_patched" else 3
    if args.dry_run:
        diff = difflib.unified_diff(original.splitlines(), patched.splitlines(), fromfile=str(target), tofile=f"{target} (patched)", lineterm="")
        print("\n".join(diff))
        return 0
    target.write_text(patched, encoding="utf-8")
    print(f"PATCHED={target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
