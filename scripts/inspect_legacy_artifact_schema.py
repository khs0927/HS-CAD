"""Inspect schema shapes of existing HS-CAD legacy JSON artifacts.

This script is review-only. It reads JSON artifacts and writes a compact schema
report. It never opens CAD apps, never calls COM, never invokes SendCommand and
never mutates source drawings.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from hscad.connectors.artifact_schema import summarize_artifact_schema
from hscad.connectors.legacy_artifact_adapter import KNOWN_ARTIFACT_KINDS


def build_schema_report(legacy_dir: str | Path) -> dict[str, Any]:
    root = Path(legacy_dir)
    artifacts: dict[str, Any] = {}
    total_record_count = 0
    warnings: list[str] = []

    for path in sorted(root.glob("*.json")):
        if path.name not in KNOWN_ARTIFACT_KINDS:
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            warnings.append(f"failed_to_read:{path.name}:{exc}")
            continue

        kind = KNOWN_ARTIFACT_KINDS[path.name]
        summary = summarize_artifact_schema(payload, kind).to_record()
        artifacts[path.name] = summary
        total_record_count += int(summary.get("record_count", 0))

    if not artifacts:
        warnings.append("no_known_legacy_artifacts_found")

    return {
        "legacy_dir": str(root),
        "artifact_count": len(artifacts),
        "total_record_count": total_record_count,
        "artifacts": artifacts,
        "warnings": warnings,
        "safety": {
            "cad_execution": False,
            "zwcad_com": False,
            "sendcommand": False,
            "xicad_alias": False,
            "original_dwg_mutation": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--legacy-dir", required=True, help="Directory containing HS-CAD JSON artifacts")
    parser.add_argument("--out", required=False, help="Optional JSON output path")
    args = parser.parse_args()

    report = build_schema_report(args.legacy_dir)
    text = json.dumps(report, ensure_ascii=False, indent=2)
    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text, encoding="utf-8")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
