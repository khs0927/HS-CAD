#!/usr/bin/env python
"""Dry-run-first cleaner for runtime artifacts that must not be committed."""

from __future__ import annotations

from pathlib import Path
import argparse
import shutil


DEFAULT_DIRS = (
    "_incoming",
    "outputs",
    ".pytest_cache",
)

DEFAULT_GLOBS = (
    "**/__pycache__",
    "**/*.pyc",
    "**/*.pyo",
)


def collect_targets(repo_root: Path) -> list[Path]:
    targets: list[Path] = []
    for rel in DEFAULT_DIRS:
        path = repo_root / rel
        if path.exists():
            targets.append(path)
    for pattern in DEFAULT_GLOBS:
        targets.extend(p for p in repo_root.glob(pattern) if p.exists())
    # De-duplicate while preserving rough order.
    unique: list[Path] = []
    seen: set[Path] = set()
    for target in targets:
        resolved = target.resolve()
        if resolved not in seen:
            unique.append(target)
            seen.add(resolved)
    return unique


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument("--apply", action="store_true", help="Delete targets. Default is dry-run.")
    args = parser.parse_args(argv)

    repo_root = args.repo_root.resolve()
    targets = collect_targets(repo_root)

    if not targets:
        print("[clean] no runtime artifacts found")
        return 0

    print("[clean] targets:")
    for target in targets:
        print(f" - {target}")

    if not args.apply:
        print("[clean] dry-run only; pass --apply to delete")
        return 0

    for target in targets:
        if not target.exists():
            continue
        if target.is_dir():
            shutil.rmtree(target)
        else:
            target.unlink(missing_ok=True)
    print("[clean] deleted runtime artifacts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
