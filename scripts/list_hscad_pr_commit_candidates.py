#!/usr/bin/env python
"""List commit candidates while excluding runtime artifacts and forbidden files."""

from __future__ import annotations

from pathlib import Path
import argparse
import fnmatch
import subprocess
import sys


EXCLUDE_PATTERNS = (
    "_incoming/**",
    "outputs/**",
    "**/__pycache__/**",
    ".pytest_cache/**",
    "*.zip",
    "*.dwg",
    "*.dxf",
    "*.pyc",
    "*.pyo",
)


def is_excluded(path: str) -> bool:
    norm = path.replace("\\", "/")
    return any(fnmatch.fnmatch(norm, pattern) for pattern in EXCLUDE_PATTERNS)


def parse_status_line(line: str) -> tuple[str, str]:
    # porcelain v1: "XY path"
    if not line:
        return "", ""
    status = line[:2].strip()
    path = line[3:] if len(line) > 3 else ""
    # rename syntax: old -> new
    if " -> " in path:
        path = path.split(" -> ", 1)[1]
    return status, path


def git_status(repo_root: Path) -> list[str]:
    result = subprocess.run(
        ["git", "status", "--short"],
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        print(result.stderr, file=sys.stderr)
        raise SystemExit(result.returncode)
    return result.stdout.splitlines()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument("--fail-on-forbidden", action="store_true")
    args = parser.parse_args(argv)

    repo_root = args.repo_root.resolve()
    candidates: list[tuple[str, str]] = []
    excluded: list[tuple[str, str]] = []

    for line in git_status(repo_root):
        status, path = parse_status_line(line)
        if not path:
            continue
        if is_excluded(path):
            excluded.append((status, path))
        else:
            candidates.append((status, path))

    print("[commit candidates]")
    for status, path in candidates:
        print(f"{status:>2} {path}")

    print("\n[excluded runtime/forbidden]")
    for status, path in excluded:
        print(f"{status:>2} {path}")

    if args.fail_on_forbidden and excluded:
        print("\n[ERROR] forbidden/runtime files are present in git status; clean before commit", file=sys.stderr)
        return 4

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
