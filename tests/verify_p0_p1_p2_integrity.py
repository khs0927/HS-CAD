from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.integrations.xicad_rule_engine import XiCadRuleEngine

DEFAULT_THRESHOLDS = {"shortkeys": 300, "pgp_aliases": 300, "steel_specs": 100, "block_catalog": 500}


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify P0/P1/P2 XiCAD rule extraction integrity.")
    parser.add_argument("--xicad-root", default="C:/xicad")
    parser.add_argument("--out", default="outputs/xicad_integrity_report.json")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()
    engine = XiCadRuleEngine(args.xicad_root)
    rules = engine.load_all()
    summary = engine.summarize(rules)
    checks = {}
    for key, threshold in DEFAULT_THRESHOLDS.items():
        value = int(summary.get(key, 0) or 0)
        checks[key] = {"value": value, "threshold": threshold, "passed": value >= threshold}
    protected = int(summary.get("protected_lisp_files", 0) or 0)
    checks["protected_lisp_files_detected"] = {"value": protected, "threshold": 1, "passed": protected >= 1}
    report = {
        "xicad_root": args.xicad_root,
        "summary": summary,
        "checks": checks,
        "success": all(item["passed"] for item in checks.values()),
        "notes": [
            "P0: shortkey mapping and protected LISP isolation",
            "P1: PGP aliases and steel .dat specs",
            "P2: Lib DWG block catalog indexing",
            "ASCII console output only for CP949 Windows terminals.",
        ],
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print("=" * 80)
    print("HS-CAD XiCAD P0/P1/P2 Integrity Audit")
    print("=" * 80)
    for key, item in checks.items():
        status = "PASS" if item["passed"] else "FAIL"
        print(f"{status}: {key}: {item['value']} / threshold {item['threshold']}")
    print(f"Report: {out}")
    print("SUCCESS" if report["success"] else "FAILED")
    if args.strict and not report["success"]:
        return 1
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
