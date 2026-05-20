from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.testing.environment_check import run_environment_check, summarize_environment_check, write_environment_check


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify Python/ZWCAD 2025/2026/XiCAD environment before integration testing.")
    parser.add_argument("--version", choices=["2025", "2026"], help="Preferred ZWCAD version")
    parser.add_argument("--dwg", help="Optional sample DWG path")
    parser.add_argument("--xicad-root", help="Optional XiCAD root path")
    parser.add_argument("--out-dir", default="outputs/zwcad_env_check", help="Output directory")
    parser.add_argument("--start-zwcad", action="store_true", help="Allow CreateObject to start ZWCAD if no active instance is found")
    args = parser.parse_args()

    payload = run_environment_check(
        dwg=args.dwg,
        xicad_root=args.xicad_root,
        version=args.version,
        start_zwcad=args.start_zwcad,
        project_root=PROJECT_ROOT,
    )
    write_environment_check(payload, args.out_dir)
    print(summarize_environment_check(payload))
    print(f"Wrote: {Path(args.out_dir) / 'environment_check.json'}")


if __name__ == "__main__":
    main()
