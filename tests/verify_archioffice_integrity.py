from __future__ import annotations

import argparse
import json
from pathlib import Path

from src.integrations.archioffice_rule_engine import ArchiOfficeRuleEngine


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify parseable ArchiOffice rule assets without modifying CAD files.")
    parser.add_argument("--archioffice-root", default="C:/Program Files/ArchiOfficeZW2024")
    parser.add_argument("--out", default="outputs/archioffice_integrity_report.json")
    args = parser.parse_args()

    engine = ArchiOfficeRuleEngine(args.archioffice_root)
    rules = engine.load_all()
    summary = engine.summarize(rules)
    report = {
        "ok": bool(Path(args.archioffice_root).exists()),
        "summary": summary,
        "safety": {
            "save": False,
            "save_as": False,
            "purge": False,
            "decode_protected_lisp": False,
            "writes_to_archioffice_root": False,
        },
    }

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

