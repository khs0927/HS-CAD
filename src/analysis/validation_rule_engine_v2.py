from __future__ import annotations

from pathlib import Path
from typing import Any

from src.analysis.entity_loader import read_json, write_json_and_md


def run_validation_rules_v2(workspace: str | Path) -> dict[str, Any]:
    """Threshold-aware validation rule engine.

    This version reads VALIDATION_THRESHOLDS.json when present and applies permissive
    development-stage thresholds by default.
    """
    base = Path(workspace)
    thresholds_payload = read_json(base / "VALIDATION_THRESHOLDS.json")
    rules = thresholds_payload.get("rules") or {}

    max_missing = int(rules.get("max_missing_artifacts", 0))
    max_errors = int(rules.get("max_validation_errors", 0))
    max_warnings = int(rules.get("max_validation_warnings", 999))
    min_nodes = int(rules.get("min_evidence_nodes", 1))
    min_edges = int(rules.get("min_evidence_edges", 0))
    min_dashboard = int(rules.get("min_dashboard_ready_sections", 1))

    batch = read_json(base / "BATCH_VALIDATION_SUMMARY.json")
    validation = read_json(base / "VALIDATION_RULE_RESULTS.json")
    evidence = read_json(base / "EVIDENCE_JOIN_FUSION.json")
    dashboard = read_json(base / "QUALITY_DASHBOARD_MANIFEST.json")

    findings = []

    missing = int((batch.get("summary") or {}).get("missing_artifact_count") or 0)
    findings.append(_finding("missing_artifacts", missing <= max_missing, f"missing={missing}, max={max_missing}"))

    old_errors = int((validation.get("summary") or {}).get("error_count") or 0)
    old_warnings = int((validation.get("summary") or {}).get("warning_count") or 0)
    findings.append(_finding("validation_error_count", old_errors <= max_errors, f"errors={old_errors}, max={max_errors}"))
    findings.append(_finding("validation_warning_count", old_warnings <= max_warnings, f"warnings={old_warnings}, max={max_warnings}"))

    node_count = int((evidence.get("summary") or {}).get("node_count") or 0)
    edge_count = int((evidence.get("summary") or {}).get("edge_count") or 0)
    findings.append(_finding("evidence_min_nodes", node_count >= min_nodes, f"nodes={node_count}, min={min_nodes}"))
    findings.append(_finding("evidence_min_edges", edge_count >= min_edges, f"edges={edge_count}, min={min_edges}"))

    ready_sections = int((dashboard.get("summary") or {}).get("ready_section_count") or 0)
    findings.append(_finding("dashboard_ready_sections", ready_sections >= min_dashboard, f"ready={ready_sections}, min={min_dashboard}"))

    failed = [row for row in findings if row["status"] == "fail"]
    payload = {
        "backend": "validation_rule_engine_v2",
        "schema_version": "0.1",
        "summary": {
            "rule_count": len(findings),
            "fail_count": len(failed),
            "overall_status": "pass" if not failed else "warning",
        },
        "thresholds": rules,
        "findings": findings,
        "todo": [
            "Split warnings/errors after real baseline calibration.",
            "Add discipline-specific thresholds.",
            "Add severity to each threshold rule.",
            "Wire this v2 engine into the main evidence worker after validation.",
        ],
        "warnings": [row["message"] for row in failed],
    }
    return write_json_and_md(base, "VALIDATION_RULE_RESULTS_V2", payload, _markdown(payload))


def _finding(rule_id: str, passed: bool, message: str) -> dict[str, Any]:
    return {
        "rule_id": rule_id,
        "status": "pass" if passed else "fail",
        "message": message,
    }


def _markdown(payload: dict[str, Any]) -> str:
    s = payload.get("summary") or {}
    lines = [
        "# Validation Rule Results V2",
        "",
        f"- Overall status: `{s.get('overall_status')}`",
        f"- Rule count: `{s.get('rule_count')}`",
        f"- Fail count: `{s.get('fail_count')}`",
        "",
        "| Rule | Status | Message |",
        "|---|---|---|",
    ]
    for row in payload.get("findings") or []:
        lines.append(f"| {row.get('rule_id')} | {row.get('status')} | {row.get('message')} |")
    lines.append("")
    return "\n".join(lines)
