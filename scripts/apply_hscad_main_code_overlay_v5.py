from __future__ import annotations

import argparse
import shutil
from dataclasses import dataclass
from pathlib import Path

EXCLUDE_DIRS = {
    ".git", "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache",
    "outputs", "_incoming",
}
EXCLUDE_SUFFIXES = {
    ".zip", ".dwg", ".dxf", ".pyc", ".pyo", ".sqlite", ".sqlite3", ".db",
}

@dataclass(frozen=True)
class CopyPlan:
    source: Path
    target: Path
    action: str

def should_skip(path: Path) -> bool:
    parts = set(path.parts)
    if parts & EXCLUDE_DIRS:
        return True
    if path.suffix.lower() in EXCLUDE_SUFFIXES:
        return True
    if path.name in {"MANIFEST.json"}:
        return False
    return False

def build_plan(overlay: Path, repo_root: Path) -> list[CopyPlan]:
    plan: list[CopyPlan] = []
    for source in sorted(overlay.rglob("*")):
        if not source.is_file():
            continue
        rel = source.relative_to(overlay)
        if rel.parts and rel.parts[0] == "scripts" and source.name == Path(__file__).name:
            # still copy this script; useful to keep provenance in repo scripts
            pass
        if should_skip(rel):
            continue
        target = repo_root / rel
        action = "update" if target.exists() else "create"
        plan.append(CopyPlan(source=source, target=target, action=action))
    return plan

def main() -> int:
    parser = argparse.ArgumentParser(description="Apply HS-CAD main-code overlay v5 safely.")
    parser.add_argument("--overlay", required=True, type=Path)
    parser.add_argument("--repo-root", required=True, type=Path)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    overlay = args.overlay.resolve()
    repo_root = args.repo_root.resolve()
    plan = build_plan(overlay, repo_root)

    for item in plan:
        rel = item.target.relative_to(repo_root)
        print(f"{item.action:7s} {rel}")

    if args.dry_run:
        print(f"DRY_RUN: {len(plan)} files planned.")
        return 0

    for item in plan:
        item.target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(item.source, item.target)

    print(f"APPLIED: {len(plan)} files copied.")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
