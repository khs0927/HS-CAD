"""Safely apply this overlay into a local HS-CAD repository.

The script refuses to copy runtime outputs, caches, zips and CAD binary/source
fixtures unless they are explicitly whitelisted under tests/fixtures.
"""
from __future__ import annotations

import argparse
import shutil
from pathlib import Path

BLOCKED_PARTS = {".git", "__pycache__", ".pytest_cache", "outputs", "_incoming"}
BLOCKED_SUFFIXES = {".zip", ".pyc", ".pyo", ".dwg"}
ALLOWED_DXF_FIXTURES = {Path("tests/fixtures/minimal_floorplan.dxf")}


def iter_files(overlay: Path):
    for path in overlay.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(overlay)
        if any(part in BLOCKED_PARTS for part in rel.parts):
            continue
        if path.suffix.lower() in BLOCKED_SUFFIXES:
            continue
        if path.suffix.lower() == ".dxf" and rel not in ALLOWED_DXF_FIXTURES:
            continue
        yield rel, path


def apply(overlay: Path, repo_root: Path, dry_run: bool = False) -> list[str]:
    actions: list[str] = []
    for rel, src in iter_files(overlay):
        dst = repo_root / rel
        action = "update" if dst.exists() else "create"
        actions.append(f"{action}: {rel.as_posix()}")
        if not dry_run:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
    return actions


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--overlay", required=True)
    parser.add_argument("--repo-root", required=True)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    actions = apply(Path(args.overlay).resolve(), Path(args.repo_root).resolve(), args.dry_run)
    for action in actions:
        print(action)
    print(f"TOTAL={len(actions)} DRY_RUN={args.dry_run}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
