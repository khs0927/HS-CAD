"""Apply HS-CAD main-code overlay v2 safely."""
from __future__ import annotations

import argparse
import shutil
from pathlib import Path

EXCLUDED_PARTS = {".git", "outputs", "__pycache__", ".pytest_cache", "_incoming"}
EXCLUDED_SUFFIXES = {".pyc", ".pyo", ".zip", ".dwg", ".dxf"}
APPLY_ROOT_ALLOWLIST = {"src", "hscad", "tests", "scripts", "docs", ".github", "APPLY_INSTRUCTIONS.md", "LOCAL_AGENT_PROMPT.md", "CODEX_MAIN_CODE_V2_PROMPT.md", "MANIFEST.json"}


def should_copy(path: Path, overlay: Path) -> bool:
    rel = path.relative_to(overlay)
    if any(part in EXCLUDED_PARTS for part in rel.parts):
        return False
    if path.is_dir():
        return False
    if rel.parts and rel.parts[0] not in APPLY_ROOT_ALLOWLIST:
        return False
    if path.suffix.lower() in EXCLUDED_SUFFIXES:
        return False
    return True


def iter_files(overlay: Path):
    for path in sorted(overlay.rglob("*")):
        if should_copy(path, overlay):
            yield path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--overlay", required=True)
    parser.add_argument("--repo-root", required=True)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--remove-legacy-dxf-fixture", action="store_true", help="Remove tests/fixtures/minimal_floorplan.dxf if present. Does not touch other DXF files.")
    args = parser.parse_args()
    overlay = Path(args.overlay).resolve(); repo = Path(args.repo_root).resolve()
    if not overlay.exists() or not repo.exists():
        raise SystemExit("overlay and repo-root must exist")
    planned = []
    for src in iter_files(overlay):
        rel = src.relative_to(overlay); dst = repo / rel
        action = "update" if dst.exists() else "create"
        planned.append((action, rel, src, dst)); print(f"{action}: {rel}")
    legacy_fixture = repo / "tests" / "fixtures" / "minimal_floorplan.dxf"
    if args.remove_legacy_dxf_fixture and legacy_fixture.exists():
        print(f"delete: {legacy_fixture.relative_to(repo)}")
    if args.dry_run:
        print(f"DRY_RUN files={len(planned)}"); return 0
    for _, _, src, dst in planned:
        dst.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(src, dst)
    if args.remove_legacy_dxf_fixture and legacy_fixture.exists():
        legacy_fixture.unlink()
    print(f"APPLIED files={len(planned)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
