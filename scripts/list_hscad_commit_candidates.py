"""List safe commit candidates while excluding runtime artifacts.

This helper is intentionally conservative. It helps avoid accidentally committing
outputs, caches, incoming overlays, zip files, and runtime CAD files.
"""
from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

EXCLUDED_PREFIXES = ("outputs/", "_incoming/", ".pytest_cache/", "__pycache__/")
EXCLUDED_SUFFIXES = (".zip", ".dwg", ".dxf", ".pyc")


def is_excluded(path: str) -> bool:
    p = path.replace("\\", "/")
    return p.startswith(EXCLUDED_PREFIXES) or p.endswith(EXCLUDED_SUFFIXES) or "/__pycache__/" in p or "/.pytest_cache/" in p


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".")
    args = parser.parse_args()
    repo = Path(args.repo_root)
    completed = subprocess.run(["git", "status", "--porcelain"], cwd=repo, text=True, capture_output=True, check=False)
    if completed.returncode != 0:
        print(completed.stderr)
        return completed.returncode
    safe: list[str] = []
    excluded: list[str] = []
    for line in completed.stdout.splitlines():
        if not line.strip():
            continue
        path = line[3:] if len(line) > 3 else line
        # Rename format: old -> new. Use new path for filtering.
        if " -> " in path:
            path = path.split(" -> ")[-1]
        if is_excluded(path):
            excluded.append(line)
        else:
            safe.append(line)
    print("[SAFE COMMIT CANDIDATES]")
    for item in safe:
        print(item)
    print("\n[EXCLUDED RUNTIME / ARTIFACT FILES]")
    for item in excluded:
        print(item)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
