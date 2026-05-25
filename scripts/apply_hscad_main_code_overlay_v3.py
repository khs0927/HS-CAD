from __future__ import annotations

import argparse
import shutil
from pathlib import Path

EXCLUDED_PARTS = {".git", "__pycache__", ".pytest_cache", "outputs", "_incoming"}
EXCLUDED_SUFFIXES = {".pyc", ".zip", ".dwg", ".dxf"}
ROOT_FILES = {"APPLY_INSTRUCTIONS.md", "CODEX_MAIN_CODE_V3_PROMPT.md", "LOCAL_AGENT_PROMPT.md", "MANIFEST.json"}


def should_copy(path: Path, overlay: Path) -> bool:
    rel = path.relative_to(overlay)
    if any(part in EXCLUDED_PARTS for part in rel.parts):
        return False
    if path.suffix.lower() in EXCLUDED_SUFFIXES:
        return False
    if rel.parts[0] in {"src", "scripts", "tests", "docs", "hscad"}:
        return True
    return str(rel) in ROOT_FILES


def iter_files(overlay: Path):
    for path in sorted(overlay.rglob("*")):
        if path.is_file() and should_copy(path, overlay):
            yield path


def main() -> int:
    parser = argparse.ArgumentParser(description="Apply HS-CAD main-code overlay v3")
    parser.add_argument("--overlay", required=True)
    parser.add_argument("--repo-root", required=True)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    overlay = Path(args.overlay).resolve()
    repo = Path(args.repo_root).resolve()
    actions = []
    for src in iter_files(overlay):
        rel = src.relative_to(overlay)
        dst = repo / rel
        action = "update" if dst.exists() else "create"
        actions.append((action, rel, src, dst))
    for action, rel, _src, _dst in actions:
        print(f"{action:6} {rel.as_posix()}")
    if args.dry_run:
        print(f"DRY_RUN files={len(actions)}")
        return 0
    for _action, _rel, src, dst in actions:
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
    print(f"APPLIED files={len(actions)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
