from __future__ import annotations

import argparse
import json
import shutil
import zipfile
from pathlib import Path
from typing import Any


DEFAULT_ZIP_NAMES = [
    "HS-CAD-cli-finalization-megapack.zip",
    "HS-CAD-analysis-export-megapack.zip",
    "HS-CAD-analysis-storage-megapack.zip",
    "HS-CAD-analysis-report-megapack.zip",
]


def apply_zip(zip_path: Path, repo_root: Path, *, overwrite: bool = True) -> dict[str, Any]:
    if not zip_path.exists():
        return {"zip": str(zip_path), "status": "missing", "files": []}

    written = []
    skipped = []
    with zipfile.ZipFile(zip_path, "r") as zf:
        for member in zf.infolist():
            if member.is_dir():
                continue
            rel = Path(member.filename)
            if rel.is_absolute() or ".." in rel.parts:
                skipped.append({"path": member.filename, "reason": "unsafe"})
                continue

            target = repo_root / rel
            if target.exists() and not overwrite:
                skipped.append({"path": member.filename, "reason": "exists"})
                continue

            target.parent.mkdir(parents=True, exist_ok=True)
            with zf.open(member, "r") as src, target.open("wb") as dst:
                shutil.copyfileobj(src, dst)
            written.append(member.filename)

    return {
        "zip": str(zip_path),
        "status": "ok",
        "written_count": len(written),
        "skipped_count": len(skipped),
        "written": written,
        "skipped": skipped,
    }


def apply_all(zip_dir: Path, repo_root: Path, *, overwrite: bool = True) -> dict[str, Any]:
    results = []
    for name in DEFAULT_ZIP_NAMES:
        results.append(apply_zip(zip_dir / name, repo_root, overwrite=overwrite))

    out = {
        "backend": "apply_megapack_zips",
        "zip_dir": str(zip_dir),
        "repo_root": str(repo_root),
        "overwrite": overwrite,
        "results": results,
        "todo": [
            "Run scripts/update_worker_manifest_from_fragments.py after applying all zips.",
            "Run scripts/update_main_imports.py after applying all zips.",
            "Run tests only after all code generation is complete.",
        ],
    }
    report = repo_root / "outputs" / "APPLY_MEGAPACK_ZIPS_REPORT.json"
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--zip-dir", default=".", help="Directory containing megapack zip files")
    parser.add_argument("--repo-root", default=".", help="Repository root")
    parser.add_argument("--no-overwrite", action="store_true")
    args = parser.parse_args()

    result = apply_all(Path(args.zip_dir), Path(args.repo_root), overwrite=not args.no_overwrite)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
