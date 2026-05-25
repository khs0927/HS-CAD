from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_PHASE5_PACKAGE = "PHASE5_DOMAIN_RULE_INPUT_PACKAGE.json"


@dataclass(frozen=True)
class Phase6NormalizedFinding:
    id: str
    source: str
    title: str
    status: str
    severity: str
    reason: str
    evidence_refs: list[str] = field(default_factory=list)
    blocked_reasons: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class Phase6ReviewAction:
    id: str
    source_finding_id: str
    action_type: str
    status: str
    review_required: bool
    execution_allowed: bool
    command_hint: str
    reason: str
    required_evidence: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class Phase6WorkflowAdapterReport:
    workspace: str
    generated_at: str
    status: str
    source_phase5_package: str
    normalized_findings: list[Phase6NormalizedFinding]
    review_actions: list[Phase6ReviewAction]
    domain_rule_decision_input: dict[str, Any]
    warnings: list[str]
    safety: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "workspace": self.workspace,
            "generated_at": self.generated_at,
            "status": self.status,
            "source_phase5_package": self.source_phase5_package,
            "normalized_findings": [item.to_dict() for item in self.normalized_findings],
            "review_actions": [item.to_dict() for item in self.review_actions],
            "domain_rule_decision_input": self.domain_rule_decision_input,
            "warnings": self.warnings,
            "safety": self.safety,
        }


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def build_phase6_domain_rule_workflow_adapter(
    workspace: str | Path,
    *,
    phase5_package_path: str | Path | None = None,
) -> Phase6WorkflowAdapterReport:
    workspace_path = Path(workspace)
    package_path = Path(phase5_package_path) if phase5_package_path else workspace_path / DEFAULT_PHASE5_PACKAGE

    warnings: list[str] = []
    findings: list[Phase6NormalizedFinding] = []
    actions: list[Phase6ReviewAction] = []

    if not package_path.exists():
        warnings.append(f"Phase5 domain rule input package missing: {package_path}")
        findings.append(
            Phase6NormalizedFinding(
                id="phase6:finding:missing-phase5-package",
                source="phase5:missing",
                title="Missing Phase 5 domain rule input package",
                status="blocked",
                severity="warning",
                reason="PHASE5_DOMAIN_RULE_INPUT_PACKAGE.json was not found.",
                evidence_refs=[DEFAULT_PHASE5_PACKAGE],
                blocked_reasons=["missing_phase5_domain_rule_input_package"],
                tags=["phase6", "blocked", "missing-input"],
            )
        )
        domain_input = _build_decision_input(
            workspace_path,
            source=str(package_path),
            status="blocked",
            findings=findings,
            actions=actions,
            warnings=warnings,
        )
        return Phase6WorkflowAdapterReport(
            workspace=str(workspace_path),
            generated_at=utc_now_iso(),
            status="blocked",
            source_phase5_package=str(package_path),
            normalized_findings=findings,
            review_actions=actions,
            domain_rule_decision_input=domain_input,
            warnings=warnings,
            safety=_safety(),
        )

    phase5 = load_json(package_path)
    raw_findings = phase5.get("findings") or []
    raw_actions = phase5.get("action_candidates") or []
    phase5_status = str(phase5.get("status") or "review_required")

    for idx, raw in enumerate(raw_findings, start=1):
        blocked_reasons = [str(item) for item in (raw.get("blocked_reasons") or [])]
        status = str(raw.get("status") or "review_required")
        severity = "warning" if blocked_reasons or status == "blocked" else "info"
        finding = Phase6NormalizedFinding(
            id=str(raw.get("finding_id") or raw.get("id") or f"phase6:finding:{idx}"),
            source=str(raw.get("source_decision_id") or raw.get("source") or "phase5"),
            title=str(raw.get("title") or f"Phase 6 finding {idx}"),
            status="blocked" if blocked_reasons or status == "blocked" else "ready_for_review",
            severity=severity,
            reason=str(raw.get("reason") or ""),
            evidence_refs=[str(item) for item in (raw.get("evidence_refs") or raw.get("required_evidence") or [])],
            blocked_reasons=blocked_reasons,
            tags=[str(item) for item in (raw.get("tags") or [])] + ["phase6-normalized"],
        )
        findings.append(finding)

    for idx, raw in enumerate(raw_actions, start=1):
        execution_allowed = bool(raw.get("execution_allowed", False))
        if execution_allowed:
            warnings.append(f"Execution flag was forced off for action: {raw.get('action_id') or idx}")

        source_finding_id = str(raw.get("source_finding_id") or "")
        action = Phase6ReviewAction(
            id=str(raw.get("action_id") or raw.get("id") or f"phase6:action:{idx}"),
            source_finding_id=source_finding_id,
            action_type=str(raw.get("action_type") or "domain-rule-review"),
            status="review_required",
            review_required=True,
            execution_allowed=False,
            command_hint=str(raw.get("command_hint") or "domain-rule-decision --review-only"),
            reason=str(raw.get("reason") or "Review-only action normalized for Domain Rule Decision Workflow."),
            required_evidence=[str(item) for item in (raw.get("required_evidence") or [])],
        )
        actions.append(action)

    if not findings:
        warnings.append("No findings found in Phase5 package.")
        findings.append(
            Phase6NormalizedFinding(
                id="phase6:finding:no-findings",
                source="phase5:none",
                title="No Phase 5 findings",
                status="blocked",
                severity="warning",
                reason="Phase5 package exists, but contains no findings.",
                blocked_reasons=["empty_phase5_findings"],
                tags=["phase6", "blocked", "empty-input"],
            )
        )

    if not actions:
        warnings.append("No review actions found in Phase5 package.")

    status = "ready_for_review" if actions else "blocked"
    if phase5_status == "blocked" or any(item.blocked_reasons for item in findings):
        status = "partial" if actions else "blocked"

    domain_input = _build_decision_input(
        workspace_path,
        source=str(package_path),
        status=status,
        findings=findings,
        actions=actions,
        warnings=warnings,
        phase5=phase5,
    )

    return Phase6WorkflowAdapterReport(
        workspace=str(workspace_path),
        generated_at=utc_now_iso(),
        status=status,
        source_phase5_package=str(package_path),
        normalized_findings=findings,
        review_actions=actions,
        domain_rule_decision_input=domain_input,
        warnings=warnings,
        safety=_safety(),
    )


def _build_decision_input(
    workspace: Path,
    *,
    source: str,
    status: str,
    findings: list[Phase6NormalizedFinding],
    actions: list[Phase6ReviewAction],
    warnings: list[str],
    phase5: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "task": "phase6_domain_rule_workflow_adapter",
        "status": status,
        "workspace": str(workspace),
        "source_phase5_package": source,
        "domain_rule_mode": "review_only",
        "findings": [item.to_dict() for item in findings],
        "review_actions": [item.to_dict() for item in actions],
        "blocked_findings": [item.to_dict() for item in findings if item.blocked_reasons],
        "ready_findings": [item.to_dict() for item in findings if not item.blocked_reasons and item.status != "blocked"],
        "review_checklist": [
            "Confirm this package is generated from derived artifacts only.",
            "Confirm all actions are review_required.",
            "Confirm execution_allowed is false for every action.",
            "Confirm blocked findings do not produce executable actions.",
            "Run Domain Rule Decision Workflow in review-only mode only.",
        ],
        "warnings": warnings,
        "source_metrics": (phase5 or {}).get("metrics", []),
        "safety": _safety(),
    }


def _safety() -> dict[str, Any]:
    return {
        "source_mutation_allowed": False,
        "cad_execution_allowed": False,
        "zwcad_com_allowed": False,
        "sendcommand_allowed": False,
        "xicad_alias_execution_allowed": False,
        "execution_allowed": False,
        "domain_rule_review_only": True,
        "command_plan_execution_allowed": False,
        "derived_artifacts_only": True,
    }


def render_phase6_markdown(report: Phase6WorkflowAdapterReport) -> str:
    data = report.to_dict()
    lines = [
        "# HS-CAD Phase 6 Domain Rule Workflow Adapter Report",
        "",
        "## Summary",
        "",
        f"- Workspace: `{data['workspace']}`",
        f"- Status: `{data['status']}`",
        f"- Source Phase 5 package: `{data['source_phase5_package']}`",
        f"- Normalized findings: `{len(data['normalized_findings'])}`",
        f"- Review actions: `{len(data['review_actions'])}`",
        "",
        "## Normalized Findings",
        "",
    ]

    for finding in data["normalized_findings"]:
        lines.append(f"- `{finding['id']}` | status=`{finding['status']}` | severity=`{finding['severity']}` | {finding['title']}")

    lines += ["", "## Review Actions", ""]
    if data["review_actions"]:
        for action in data["review_actions"]:
            lines.append(
                f"- `{action['id']}` | source=`{action['source_finding_id']}` | command_hint=`{action['command_hint']}` | execution=`{action['execution_allowed']}`"
            )
    else:
        lines.append("- None")

    lines += ["", "## Safety", ""]
    for key, value in data["safety"].items():
        lines.append(f"- `{key}`: `{value}`")

    lines += ["", "## Warnings", ""]
    if data["warnings"]:
        lines.extend(f"- {warning}" for warning in data["warnings"])
    else:
        lines.append("- None")

    return "\n".join(lines).rstrip() + "\n"


def write_phase6_adapter_outputs(
    workspace: str | Path,
    *,
    phase5_package_path: str | Path | None = None,
    out_dir: str | Path | None = None,
) -> dict[str, Any]:
    workspace_path = Path(workspace)
    out_path = Path(out_dir) if out_dir else workspace_path
    out_path.mkdir(parents=True, exist_ok=True)

    report = build_phase6_domain_rule_workflow_adapter(
        workspace_path,
        phase5_package_path=phase5_package_path,
    )
    payload = report.to_dict()

    report_json = out_path / "PHASE6_DOMAIN_RULE_WORKFLOW_ADAPTER.json"
    report_md = out_path / "PHASE6_DOMAIN_RULE_WORKFLOW_ADAPTER.md"
    decision_input_json = out_path / "DOMAIN_RULE_DECISION_INPUT_FROM_PHASE6.json"

    report_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    report_md.write_text(render_phase6_markdown(report), encoding="utf-8")
    decision_input_json.write_text(
        json.dumps(report.domain_rule_decision_input, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    return {
        "status": report.status,
        "workspace": str(workspace_path),
        "out_dir": str(out_path),
        "report_json": str(report_json),
        "report_md": str(report_md),
        "domain_rule_decision_input": str(decision_input_json),
        "warnings": report.warnings,
        "safety": report.safety,
    }
