from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_PHASE3_REPORT = "PHASE3_REAL_DATA_BINDING_REPORT.json"


@dataclass(frozen=True)
class Phase4Metric:
    key: str
    value: int | float | str | bool
    source: str
    severity: str = "info"
    note: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class Phase4DecisionCandidate:
    decision_id: str
    title: str
    status: str
    reason: str
    required_evidence: list[str] = field(default_factory=list)
    blocked_reasons: list[str] = field(default_factory=list)
    recommended_next_step: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class Phase4BridgeReport:
    workspace: str
    generated_at: str
    status: str
    source_phase3_report: str
    metrics: list[Phase4Metric]
    decision_candidates: list[Phase4DecisionCandidate]
    warnings: list[str]
    safety: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "workspace": self.workspace,
            "generated_at": self.generated_at,
            "status": self.status,
            "source_phase3_report": self.source_phase3_report,
            "metrics": [item.to_dict() for item in self.metrics],
            "decision_candidates": [item.to_dict() for item in self.decision_candidates],
            "warnings": self.warnings,
            "safety": self.safety,
        }


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def build_phase4_bridge_report(
    workspace: str | Path,
    *,
    phase3_report_path: str | Path | None = None,
) -> Phase4BridgeReport:
    workspace_path = Path(workspace)
    report_path = Path(phase3_report_path) if phase3_report_path else workspace_path / DEFAULT_PHASE3_REPORT

    warnings: list[str] = []
    metrics: list[Phase4Metric] = []
    decisions: list[Phase4DecisionCandidate] = []

    if not report_path.exists():
        warnings.append(f"Phase3 report missing: {report_path}")
        return Phase4BridgeReport(
            workspace=str(workspace_path),
            generated_at=utc_now_iso(),
            status="warning",
            source_phase3_report=str(report_path),
            metrics=[
                Phase4Metric(
                    key="phase3_report_found",
                    value=False,
                    source=str(report_path),
                    severity="warning",
                    note="Phase 4 bridge cannot compute real metrics without Phase 3 coverage report.",
                )
            ],
            decision_candidates=[
                Phase4DecisionCandidate(
                    decision_id="phase4:missing-phase3-report",
                    title="Run Phase 3 real-data binding first",
                    status="blocked",
                    reason="PHASE3_REAL_DATA_BINDING_REPORT.json was not found.",
                    required_evidence=[DEFAULT_PHASE3_REPORT],
                    blocked_reasons=["missing_phase3_report"],
                    recommended_next_step="Run hscad-analysis-phase3-bind or the Phase 3 worker.",
                )
            ],
            warnings=warnings,
            safety=_safety(),
        )

    data = load_json(report_path)
    phase3_metrics = data.get("metrics") or {}
    groups = data.get("groups") or {}
    safety = data.get("safety") or {}

    discovered = int(phase3_metrics.get("discovered_artifact_count") or data.get("discovered_count") or 0)
    missing = int(phase3_metrics.get("missing_artifact_count") or data.get("missing_count") or 0)
    json_loadable = int(phase3_metrics.get("json_loadable_artifact_count") or data.get("json_loadable_count") or 0)
    expected = int(phase3_metrics.get("expected_artifact_count") or discovered + missing or 0)
    coverage_ratio = float(phase3_metrics.get("coverage_ratio") or (discovered / expected if expected else 0))

    metrics.extend(
        [
            Phase4Metric("expected_artifact_count", expected, str(report_path)),
            Phase4Metric("discovered_artifact_count", discovered, str(report_path)),
            Phase4Metric("missing_artifact_count", missing, str(report_path), severity="warning" if missing else "info"),
            Phase4Metric("json_loadable_artifact_count", json_loadable, str(report_path)),
            Phase4Metric("coverage_ratio", round(coverage_ratio, 4), str(report_path), severity="warning" if coverage_ratio < 0.4 else "info"),
            Phase4Metric("group_count", len(groups), str(report_path)),
            Phase4Metric(
                "safe_to_connect_to_decision_package",
                bool(discovered > 0 and json_loadable > 0 and safety.get("source_mutation_allowed") is False),
                str(report_path),
            ),
        ]
    )

    groups_with_artifacts = [name for name, summary in groups.items() if int(summary.get("discovered") or 0) > 0]
    groups_without_artifacts = [name for name, summary in groups.items() if int(summary.get("discovered") or 0) == 0]

    if groups_without_artifacts:
        warnings.append(f"Groups without artifacts: {', '.join(groups_without_artifacts)}")

    decisions.append(
        Phase4DecisionCandidate(
            decision_id="phase4:decision-package-readiness",
            title="Decision package readiness from real analysis artifacts",
            status="ready_for_review" if discovered > 0 and json_loadable > 0 else "blocked",
            reason=(
                "Real analysis artifacts were discovered and JSON-loadable artifacts exist."
                if discovered > 0 and json_loadable > 0
                else "No usable analysis artifacts were discovered."
            ),
            required_evidence=[
                "PHASE3_REAL_DATA_BINDING_REPORT.json",
                "PHASE3_ARTIFACT_COVERAGE.json",
                *groups_with_artifacts[:10],
            ],
            blocked_reasons=[] if discovered > 0 and json_loadable > 0 else ["no_usable_analysis_artifacts"],
            recommended_next_step=(
                "Generate PHASE4_DECISION_BRIDGE_PACKAGE.json and feed it into domain-rule decision review."
                if discovered > 0 and json_loadable > 0
                else "Run Phase 1/2 analysis workers and Phase 3 binding first."
            ),
        )
    )

    decisions.append(
        Phase4DecisionCandidate(
            decision_id="phase4:missing-artifact-review",
            title="Missing artifact review",
            status="review_required" if missing > 0 else "ok",
            reason=f"{missing} expected artifacts were missing from the workspace.",
            required_evidence=groups_without_artifacts[:20],
            blocked_reasons=["missing_artifacts"] if missing > 0 and discovered == 0 else [],
            recommended_next_step="Run missing workers or mark unavailable artifacts as intentionally skipped.",
        )
    )

    status = "ok"
    if discovered == 0:
        status = "warning"
    elif missing > 0:
        status = "partial"

    return Phase4BridgeReport(
        workspace=str(workspace_path),
        generated_at=utc_now_iso(),
        status=status,
        source_phase3_report=str(report_path),
        metrics=metrics,
        decision_candidates=decisions,
        warnings=warnings,
        safety=_safety(),
    )


def _safety() -> dict[str, Any]:
    return {
        "source_mutation_allowed": False,
        "cad_execution_allowed": False,
        "zwcad_com_allowed": False,
        "sendcommand_allowed": False,
        "xicad_alias_execution_allowed": False,
        "derived_artifacts_only": True,
        "decision_package_is_review_only": True,
    }


def render_phase4_markdown(report: Phase4BridgeReport) -> str:
    data = report.to_dict()
    lines = [
        "# HS-CAD Phase 4 Metrics / Decision Bridge Report",
        "",
        "## Summary",
        "",
        f"- Workspace: `{data['workspace']}`",
        f"- Status: `{data['status']}`",
        f"- Source Phase 3 report: `{data['source_phase3_report']}`",
        "",
        "## Metrics",
        "",
    ]
    for metric in data["metrics"]:
        lines.append(f"- `{metric['key']}`: `{metric['value']}` ({metric['severity']})")

    lines += ["", "## Decision Candidates", ""]
    for decision in data["decision_candidates"]:
        lines.append(f"### {decision['decision_id']}")
        lines.append("")
        lines.append(f"- Title: {decision['title']}")
        lines.append(f"- Status: `{decision['status']}`")
        lines.append(f"- Reason: {decision['reason']}")
        if decision["blocked_reasons"]:
            lines.append(f"- Blocked reasons: {', '.join(decision['blocked_reasons'])}")
        lines.append(f"- Recommended next step: {decision['recommended_next_step']}")
        lines.append("")

    lines += ["## Safety", ""]
    for key, value in data["safety"].items():
        lines.append(f"- `{key}`: `{value}`")

    lines += ["", "## Warnings", ""]
    if data["warnings"]:
        lines.extend(f"- {warning}" for warning in data["warnings"])
    else:
        lines.append("- None")

    return "\n".join(lines).rstrip() + "\n"


def write_phase4_bridge_outputs(
    workspace: str | Path,
    *,
    phase3_report_path: str | Path | None = None,
    out_dir: str | Path | None = None,
) -> dict[str, Any]:
    workspace_path = Path(workspace)
    out_path = Path(out_dir) if out_dir else workspace_path
    out_path.mkdir(parents=True, exist_ok=True)

    report = build_phase4_bridge_report(workspace_path, phase3_report_path=phase3_report_path)
    payload = report.to_dict()

    report_json = out_path / "PHASE4_METRICS_DECISION_BRIDGE.json"
    report_md = out_path / "PHASE4_METRICS_DECISION_BRIDGE.md"
    decision_json = out_path / "PHASE4_DECISION_BRIDGE_PACKAGE.json"

    report_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    report_md.write_text(render_phase4_markdown(report), encoding="utf-8")
    decision_json.write_text(
        json.dumps(
            {
                "task": "phase4_metrics_decision_bridge",
                "status": report.status,
                "source_phase3_report": report.source_phase3_report,
                "metrics": [metric.to_dict() for metric in report.metrics],
                "decision_candidates": [item.to_dict() for item in report.decision_candidates],
                "warnings": report.warnings,
                "safety": report.safety,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    return {
        "status": report.status,
        "workspace": str(workspace_path),
        "out_dir": str(out_path),
        "report_json": str(report_json),
        "report_md": str(report_md),
        "decision_bridge_package": str(decision_json),
        "warnings": report.warnings,
        "safety": report.safety,
    }
