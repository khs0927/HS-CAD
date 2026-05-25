from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.analysis.entity_loader import read_json, write_json_and_md


DEFAULT_VALIDATION_THRESHOLDS: dict[str, Any] = {
    "schema_version": "0.1",
    "rules": {
        "max_missing_artifacts": 0,
        "max_validation_errors": 0,
        "max_validation_warnings": 999,
        "min_evidence_nodes": 1,
        "min_evidence_edges": 0,
        "min_dashboard_ready_sections": 1,
        "allow_scaffold_warnings": True,
    },
}


def load_or_create_validation_thresholds(workspace: str | Path) -> dict[str, Any]:
    """Load or create VALIDATION_THRESHOLDS.json.

    This is intentionally permissive for the fast-generation phase.
    Real thresholds must be calibrated after webhard batch validation.
    """
    base = Path(workspace)
    threshold_path = base / "VALIDATION_THRESHOLDS.json"
    if threshold_path.exists():
        payload = read_json(threshold_path)
        source = "existing"
    else:
        payload = DEFAULT_VALIDATION_THRESHOLDS
        threshold_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        source = "created_default"

    report = {
        "backend": "validation_threshold_config",
        "schema_version": "0.1",
        "summary": {
            "source": source,
            "path": str(threshold_path),
            "rule_count": len((payload.get("rules") or {})),
        },
        "thresholds": payload,
        "todo": [
            "Calibrate thresholds with outputs/webhard_batch_100.",
            "Add discipline-specific thresholds.",
            "Add project/company profile threshold overlays.",
            "Wire these thresholds into validation_rule_engine.",
        ],
        "warnings": [
            "Default thresholds are permissive and intended for development scaffolds."
        ],
    }
    return write_json_and_md(base, "VALIDATION_THRESHOLD_CONFIG", report, _markdown(report))


def _markdown(payload: dict[str, Any]) -> str:
    s = payload.get("summary") or {}
    lines = [
        "# Validation Threshold Config",
        "",
        f"- Source: `{s.get('source')}`",
        f"- Path: `{s.get('path')}`",
        f"- Rule count: `{s.get('rule_count')}`",
        "",
        "## Rules",
        "",
        "| Rule | Value |",
        "|---|---|",
    ]
    for key, value in ((payload.get("thresholds") or {}).get("rules") or {}).items():
        lines.append(f"| {key} | `{value}` |")
    lines.append("")
    return "\n".join(lines)
