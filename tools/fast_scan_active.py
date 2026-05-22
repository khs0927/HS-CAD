from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.adapters.zwcad_com_adapter import ZWCADCOMAdapter
from src.scanners.native_fast_scan import fast_scan_active


def main() -> None:
    parser = argparse.ArgumentParser(description="Fast-scan the active ZWCAD drawing without a full ModelSpace COM walk.")
    parser.add_argument("--out", default="generated/fast_scan_report.json", help="Output JSON path")
    args = parser.parse_args()

    adapter = ZWCADCOMAdapter(visible=True)
    adapter.connect()
    payload = fast_scan_active(adapter)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Fast scan written: {out}")


if __name__ == "__main__":
    main()
