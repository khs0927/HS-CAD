from __future__ import annotations

import argparse
import shutil
from pathlib import Path

EXCLUDE_DIRS = {"vendor", "outputs", "backups", "generated", "__pycache__", ".pytest_cache", ".git", ".venv", "venv", "env"}
EXCLUDE_SUFFIXES = {".dwg", ".dxf", ".bak", ".tmp", ".pyc"}
EXCLUDE_FILES = {"tools_build_notice.tmp", ".env"}


def should_skip(path: Path, root: Path, include_vendor: bool = False, include_tests: bool = True, include_docs: bool = True) -> bool:
    rel = path.relative_to(root)
    parts = set(rel.parts)
    if include_vendor:
        parts.discard("vendor")
    if include_tests:
        parts.discard("tests")
    if include_docs:
        parts.discard("docs")
    if parts & EXCLUDE_DIRS:
        return True
    if not include_tests and "tests" in rel.parts:
        return True
    if not include_docs and "docs" in rel.parts:
        return True
    if path.name in EXCLUDE_FILES:
        return True
    if path.suffix.lower() in EXCLUDE_SUFFIXES:
        return True
    return False


def prepare_public_release(source: Path, out: Path, include_vendor: bool = False, include_tests: bool = True, include_docs: bool = True, dry_run: bool = False) -> list[Path]:
    source = source.resolve()
    out = out.resolve()
    copied: list[Path] = []
    if out.exists() and not dry_run:
        shutil.rmtree(out)
    for path in source.rglob("*"):
        if should_skip(path, source, include_vendor=include_vendor, include_tests=include_tests, include_docs=include_docs):
            continue
        rel = path.relative_to(source)
        target = out / rel
        if path.is_dir():
            if not dry_run:
                target.mkdir(parents=True, exist_ok=True)
            continue
        copied.append(rel)
        if not dry_run:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target)
    if not dry_run:
        (out / "README_PUBLIC.md").write_text(
            "# ZWCAD AI Modifier Public Release\n\n"
            "This public package intentionally excludes `vendor/xicad`. Install XiCAD locally and set its path in `config/xicad_profile.example.yaml`.\n",
            encoding="utf-8",
        )
        notice = source / "LICENSE_NOTICE.md"
        if notice.exists():
            shutil.copy2(notice, out / "LICENSE_NOTICE.md")
        example = out / "config" / "xicad_profile.example.yaml"
        example.parent.mkdir(parents=True, exist_ok=True)
        example.write_text("xicad_root: C:/xicad\nuse_vendor_xicad: false\n", encoding="utf-8")
        (out / "PACKAGE_PUBLIC_CONTENTS.txt").write_text("\n".join(str(p) for p in copied), encoding="utf-8")
    return copied


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare a public GitHub release without bundled XiCAD vendor files.")
    parser.add_argument("--source", default=".", help="Project source root")
    parser.add_argument("--out", required=True, help="Output directory")
    parser.add_argument("--include-vendor", action="store_true", help="Include vendor directory; not recommended for public GitHub")
    parser.add_argument("--include-tests", action=argparse.BooleanOptionalAction, default=True, help="Include tests in the public package")
    parser.add_argument("--include-docs", action=argparse.BooleanOptionalAction, default=True, help="Include docs in the public package")
    parser.add_argument("--dry-run", action="store_true", help="Print files that would be copied")
    args = parser.parse_args()
    copied = prepare_public_release(Path(args.source), Path(args.out), include_vendor=args.include_vendor, include_tests=args.include_tests, include_docs=args.include_docs, dry_run=args.dry_run)
    print(f"Prepared file count: {len(copied)}")
    if args.dry_run:
        for rel in copied[:200]:
            print(rel)


if __name__ == "__main__":
    main()
