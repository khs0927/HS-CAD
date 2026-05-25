#!/usr/bin/env python
"""Apply HS-CAD main-code overlay v4 with dry-run support."""

from __future__ import annotations

from pathlib import Path
import argparse
import shutil


EXCLUDE_DIRS = {"__pycache__", ".pytest_cache", "outputs", "_incoming"}
EXCLUDE_SUFFIXES = {".pyc", ".pyo", ".zip", ".dwg", ".dxf"}


def iter_overlay_files(overlay: Path):
    for path in overlay.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(overlay)
        parts = set(rel.parts)
        if parts & EXCLUDE_DIRS:
            continue
        if path.suffix.lower() in EXCLUDE_SUFFIXES:
            continue
        yield path, rel


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--overlay", type=Path, required=True)
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    overlay = args.overlay.resolve()
    repo_root = args.repo_root.resolve()
    files = list(iter_overlay_files(overlay))

    for src, rel in files:
        dst = repo_root / rel
        action = "update" if dst.exists() else "create"
        print(f"{action:>6} {rel}")

    if args.dry_run:
        print(f"[apply_v4] dry-run: {len(files)} file(s)")
        return 0

    for src, rel in files:
        dst = repo_root / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)

    print(f"[apply_v4] applied {len(files)} file(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
