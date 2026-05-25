from __future__ import annotations

import argparse
import json
import shutil
import zipfile
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass
class AppliedFile:
    source: str
    target: str
    action: str
    reason: str = ""


class CombinedMegapackApplier:
    """Safely stage generated megapack files into an HS-CAD checkout.

    This script intentionally avoids automatic edits to high-risk integration files:
    - src/main.py
    - config/worker_manifest.json

    Root-level README/PATCH/manifest files from each source pack are preserved under
    docs/megapacks/<pack>/ so the generated patch instructions remain reviewable.
    """

    HIGH_RISK_TARGETS = {
        "src/main.py",
        "config/worker_manifest.json",
    }

    def __init__(self, zip_path: Path, repo_root: Path, mode: str = "staged") -> None:
        self.zip_path = zip_path
        self.repo_root = repo_root
        self.mode = mode
        self.applied: list[AppliedFile] = []
        self.skipped: list[AppliedFile] = []

    def run(self) -> dict:
        if not self.zip_path.exists():
            raise FileNotFoundError(f"Combined ZIP not found: {self.zip_path}")
        if not self.repo_root.exists():
            raise FileNotFoundError(f"Repo root not found: {self.repo_root}")

        with zipfile.ZipFile(self.zip_path) as zf:
            for name in zf.namelist():
                if name.endswith("/"):
                    continue
                if name.startswith("source_zips/"):
                    self._copy_source_zip(zf, name)
                    continue
                if name == "COMBINED_ZIP_MANIFEST.json":
                    self._write_member(zf, name, Path("docs/megapacks/COMBINED_ZIP_MANIFEST.json"))
                    continue
                if not name.startswith("extracted_by_zip/"):
                    self.skipped.append(AppliedFile(name, "", "skipped", "unknown ZIP member layout"))
                    continue
                self._apply_extracted_member(zf, name)

        report = {
            "zip_path": str(self.zip_path),
            "repo_root": str(self.repo_root),
            "mode": self.mode,
            "applied_count": len(self.applied),
            "skipped_count": len(self.skipped),
            "applied": [asdict(item) for item in self.applied],
            "skipped": [asdict(item) for item in self.skipped],
            "manual_follow_up": [
                "Review docs/megapacks/*/PATCH_MAIN_IMPORT*.md before editing src/main.py.",
                "Review docs/megapacks/*/PATCH_WORKER_MANIFEST*.md before editing config/worker_manifest.json.",
                "Run pytest and CLI help smoke tests before committing generated code.",
            ],
        }
        out = self.repo_root / "outputs" / "combined_megapack_apply_report.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        return report

    def _apply_extracted_member(self, zf: zipfile.ZipFile, name: str) -> None:
        parts = name.split("/")
        if len(parts) < 3:
            self.skipped.append(AppliedFile(name, "", "skipped", "invalid extracted_by_zip path"))
            return
        pack = parts[1]
        rel = Path(*parts[2:])
        rel_posix = rel.as_posix()

        if rel_posix.startswith(("src/", "docs/", "scripts/")):
            target = rel
        else:
            target = Path("docs") / "megapacks" / pack / rel

        if target.as_posix() in self.HIGH_RISK_TARGETS:
            self.skipped.append(AppliedFile(name, target.as_posix(), "skipped", "high-risk target requires manual patch"))
            return

        self._write_member(zf, name, target)

    def _copy_source_zip(self, zf: zipfile.ZipFile, name: str) -> None:
        target = Path("artifacts") / "megapacks" / Path(name).name
        self._write_member(zf, name, target, binary=True)

    def _write_member(self, zf: zipfile.ZipFile, name: str, target: Path, binary: bool = False) -> None:
        dest = self.repo_root / target
        dest.parent.mkdir(parents=True, exist_ok=True)
        data = zf.read(name)
        if binary:
            dest.write_bytes(data)
        else:
            try:
                dest.write_text(data.decode("utf-8"), encoding="utf-8")
            except UnicodeDecodeError:
                dest.write_bytes(data)
        self.applied.append(AppliedFile(name, target.as_posix(), "written"))


def main() -> None:
    parser = argparse.ArgumentParser(description="Safely apply HS-CAD combined generated megapack ZIP")
    parser.add_argument("--zip", required=True, type=Path, help="Path to HS-CAD-all-generated-megapacks-combined.zip")
    parser.add_argument("--repo-root", default=Path("."), type=Path, help="HS-CAD repository root")
    parser.add_argument("--mode", default="staged", choices=["staged"], help="Only staged mode is supported")
    args = parser.parse_args()

    report = CombinedMegapackApplier(args.zip, args.repo_root, mode=args.mode).run()
    print(json.dumps({"applied_count": report["applied_count"], "skipped_count": report["skipped_count"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
