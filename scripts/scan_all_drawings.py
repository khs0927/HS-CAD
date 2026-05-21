#!/usr/bin/env python
"""
Batch scan ZWCAD drawing files and generate architecture reports.

Scans all *.dwg files under the given root directory (default: Z:\\내 드라이브\\#웹하드)
and runs the `src.main analyze-architecture` command for each drawing.
Outputs are stored under `outputs/architecture_reports/<relative_path_without_ext>`.

Usage:
    python scripts/scan_all_drawings.py [--root "Z:\\내 드라이브\\#웹하드"] [--out "outputs/architecture_reports"]
"""

import subprocess
import sys
from pathlib import Path


def main(root_dir: Path, out_root: Path) -> None:
    dwg_files = list(root_dir.rglob("*.dwg"))
    if not dwg_files:
        print(f"No DWG files found under {root_dir}")
        return

    for dwg in dwg_files:
        # Build a relative output path mirroring the source hierarchy
        rel = dwg.relative_to(root_dir).with_suffix("")
        out_dir = out_root / rel.parent / rel.name
        out_dir.mkdir(parents=True, exist_ok=True)

        cmd = [
            sys.executable,
            "-m",
            "src.main",
            "analyze-architecture",
            "--dwg",
            str(dwg),
            "--out-dir",
            str(out_dir),
        ]
        print(f"Processing {dwg} → {out_dir}")
        subprocess.run(cmd, check=True)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Batch scan ZWCAD drawings")
    parser.add_argument(
        "--root",
        type=str,
        default=r"Z:\\내 드라이브\\#웹하드",
        help="Root directory containing DWG files",
    )
    parser.add_argument(
        "--out",
        type=str,
        default="outputs/architecture_reports",
        help="Root directory for generated reports",
    )
    args = parser.parse_args()
    main(Path(args.root), Path(args.out))
