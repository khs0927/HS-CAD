#!/usr/bin/env python3
"""Apply this overlay into an HS-CAD repository.

The script is intentionally conservative: it skips generated outputs and can run
in dry-run mode before copying files.
"""
from __future__ import annotations

import argparse
import shutil
from pathlib import Path

SKIP_TOP_LEVEL = {"README_NEXT_STAGE_OVERLAY.md", "APPLY_INSTRUCTIONS.md"}
COPY_ROOTS = {"src", "tests", "scripts", "docs", ".github"}


def iter_overlay_files(overlay: Path):
    for root_name in COPY_ROOTS:
        root = overlay / root_name
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if path.is_file():
                yield path, path.relative_to(overlay)


def apply_overlay(overlay: Path, repo_root: Path, *, dry_run: bool = False) -> list[str]:
    actions: list[str] = []
    for src, rel in iter_overlay_files(overlay):
        dst = repo_root / rel
        action = "update" if dst.exists() else "create"
        actions.append(f"{action}: {rel}")
        if not dry_run:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
    return actions


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--overlay", required=True)
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    actions = apply_overlay(Path(args.overlay).resolve(), Path(args.repo_root).resolve(), dry_run=args.dry_run)
    for action in actions:
        print(action)
    print(f"total_actions={len(actions)} dry_run={args.dry_run}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
