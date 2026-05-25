from __future__ import annotations

import argparse
import zipfile
from pathlib import Path


INCLUDE_DIRS = ["src", "docs", "config", "scripts"]
EXCLUDE_PARTS = {".git", "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache"}


def should_include(path: Path) -> bool:
    return not any(part in EXCLUDE_PARTS for part in path.parts)


def build_zip(repo_root: Path, out: Path) -> Path:
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists():
        out.unlink()

    with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for dirname in INCLUDE_DIRS:
            root = repo_root / dirname
            if not root.exists():
                continue
            for path in sorted(root.rglob("*")):
                if path.is_file() and should_include(path):
                    zf.write(path, arcname=str(path.relative_to(repo_root)))
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--out", default="outputs/HS-CAD-final-codegen-bundle.zip")
    args = parser.parse_args()
    out = build_zip(Path(args.repo_root), Path(args.out))
    print(f"created {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
