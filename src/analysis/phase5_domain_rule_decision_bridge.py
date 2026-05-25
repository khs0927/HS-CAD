from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_PHASE4_PACKAGE = "PHASE4_DECISION_BRIDGE_PACKAGE.json"


@dataclass(frozen=True)
class Phase5DomainRuleFinding:
    finding_id: str
    source_decision_id: str
    title: str
    status: str
    reason: str
    evidence_refs: list[str] = field(default_factory=list)
    blocked_reasons: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class Phase5DomainRuleActionCandidate:
    action_id: str
    source_finding_id: str
    action_type: str
    status: str
    command_hint: str
    review_required: bool = True
    execution_allowed: bool = False
    reason: str = ""
    required_evidence: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class Phase5DomainDecisionBridgeReport:
    workspace: str
    generated_at: str
    status: str
    source_phase4_package: str
    findings: list[Phase5DomainRuleFinding]
    action_candidates: list[Phase5DomainRuleActionCandidate]
    domain_rule_input_package: dict[str, Any]
    warnings: list[str]
    safety: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "workspace": self.workspace,
            "generated_at": self.generated_at,
            "status": self.status,
            "source_phase4_package": self.source_phase4_package,
            "findings": [item.to_dict() for item in self.findings],
            "action_candidates": [item.to_dict() for item in self.action_candidates],
            "domain_rule_input_package": self.domain_rule_input_package,
            "warnings": self.warnings,
            "safety": self.safety,
        }


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def build_phase5_domain_decision_bridge(
    workspace: str | Path,
    *,
    phase4_package_path: str | Path | None = None,
) -> Phase5DomainDecisionBridgeReport:
    workspace_path = Path(workspace)
    package_path = Path(phase4_package_path) if phase4_package_path else workspace_path / DEFAULT_PHASE4_PACKAGE

    warnings: list[str] = []
    findings: list[Phase5DomainRuleFinding] = []
    actions: list[Phase5DomainRuleActionCandidate] = []

    if not package_path.exists():
        warnings.append(f"Phase4 decision bridge package missing: {package_path}")
        findings.append(
            Phase5DomainRuleFinding(
                finding_id="phase5:finding:missing-phase4-package",
                source_decision_id="phase4:missing",
                title="Missing Phase 4 decision bridge package",
                status="blocked",
                reason="PHASE4_DECISION_BRIDGE_PACKAGE.json was not found.",
                evidence_refs=[DEFAULT_PHASE4_PACKAGE],
                blocked_reasons=["missing_phase4_decision_bridge_package"],
                tags=["phase5", "blocked", "missing-input"],
            )
        )
        domain_package = _domain_rule_input_package(
            workspace_path,
            findings,
            actions,
            source=str(package_path),
            status="blocked",
            warnings=warnings,
        )
        return Phase5DomainDecisionBridgeReport(
            workspace=str(workspace_path),
            generated_at=utc_now_iso(),
            status="blocked",
            source_phase4_package=str(package_path),
            findings=findings,
            action_candidates=actions,
            domain_rule_input_package=domain_package,
            warnings=warnings,
            safety=_safety(),
        )

    phase4 = load_json(package_path)
    decision_candidates = phase4.get("decision_candidates") or []
    metrics = phase4.get("metrics") or []

    for idx, item in enumerate(decision_candidates, start=1):
        decision_id = str(item.get("decision_id") or f"phase4:decision:{idx}")
        status = str(item.get("status") or "review_required")
        title = str(item.get("title") or decision_id)
        reason = str(item.get("reason") or "")
        required_evidence = [str(value) for value in (item.get("required_evidence") or [])]
        blocked_reasons = [str(value) for value in (item.get("blocked_reasons") or [])]

        finding_status = "blocked" if blocked_reasons or status == "blocked" else "ready_for_review"
        finding = Phase5DomainRuleFinding(
            finding_id=f"phase5:finding:{idx}",
            source_decision_id=decision_id,
            title=title,
            status=finding_status,
            reason=reason,
            evidence_refs=required_evidence,
            blocked_reasons=blocked_reasons,
            tags=["phase5", "domain-rule-input", status],
        )
        findings.append(finding)

        if finding_status != "blocked":
            actions.append(
                Phase5DomainRuleActionCandidate(
                    action_id=f"phase5:action:{idx}",
                    source_finding_id=finding.finding_id,
                    action_type="domain-rule-review",
                    status="review_required",
                    command_hint="domain-rule-decision --review-only",
                    review_required=True,
                    execution_allowed=False,
                    reason="Phase 5 only prepares review input for Domain Rule Decision Workflow.",
                    required_evidence=required_evidence,
                )
            )

    if not findings:
        warnings.append("No decision candidates found in Phase4 package.")
        findings.append(
            Phase5DomainRuleFinding(
                finding_id="phase5:finding:no-decision-candidates",
                source_decision_id="phase4:none",
                title="No Phase 4 decision candidates",
                status="blocked",
                reason="Phase4 package exists, but decision_candidates is empty.",
                blocked_reasons=["empty_decision_candidates"],
                tags=["phase5", "blocked", "empty-input"],
            )
        )

    if not metrics:
        warnings.append("No metrics found in Phase4 package.")

    status = "ready_for_review" if actions else "blocked"
    if any(item.blocked_reasons for item in findings) and actions:
        status = "partial"

    domain_package = _domain_rule_input_package(
        workspace_path,
        findings,
        actions,
        source=str(package_path),
        status=status,
        warnings=warnings,
        metrics=metrics,
    )

    return Phase5DomainDecisionBridgeReport(
        workspace=str(workspace_path),
        generated_at=utc_now_iso(),
        status=status,
        source_phase4_package=str(package_path),
        findings=findings,
        action_candidates=actions,
        domain_rule_input_package=domain_package,
        warnings=warnings,
        safety=_safety(),
    )


def _domain_rule_input_package(
    workspace: Path,
    findings: list[Phase5DomainRuleFinding],
    actions: list[Phase5DomainRuleActionCandidate],
    *,
    source: str,
    status: str,
    warnings: list[str],
    metrics: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return {
        "task": "phase5_domain_rule_decision_bridge",
        "status": status,
        "workspace": str(workspace),
        "source_phase4_package": source,
        "findings": [item.to_dict() for item in findings],
        "action_candidates": [item.to_dict() for item in actions],
        "metrics": metrics or [],
        "review_checklist": [
            "Confirm Phase 4 package came from derived artifacts only.",
            "Confirm findings have required evidence refs.",
            "Confirm blocked findings are not converted to executable actions.",
            "Confirm execution_allowed remains false.",
            "Run Domain Rule Decision Workflow only in review mode.",
        ],
        "warnings": warnings,
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
        "derived_artifacts_only": True,
    }


def render_phase5_markdown(report: Phase5DomainDecisionBridgeReport) -> str:
    data = report.to_dict()
    lines = [
        "# HS-CAD Phase 5 Domain Rule Decision Bridge Report",
        "",
        "## Summary",
        "",
        f"- Workspace: `{data['workspace']}`",
        f"- Status: `{data['status']}`",
        f"- Source Phase 4 package: `{data['source_phase4_package']}`",
        f"- Findings: `{len(data['findings'])}`",
        f"- Action candidates: `{len(data['action_candidates'])}`",
        "",
        "## Findings",
        "",
    ]

    for finding in data["findings"]:
        lines.append(f"### {finding['finding_id']}")
        lines.append("")
        lines.append(f"- Source decision: `{finding['source_decision_id']}`")
        lines.append(f"- Title: {finding['title']}")
        lines.append(f"- Status: `{finding['status']}`")
        lines.append(f"- Reason: {finding['reason']}")
        if finding["blocked_reasons"]:
            lines.append(f"- Blocked reasons: {', '.join(finding['blocked_reasons'])}")
        lines.append("")

    lines += ["## Action Candidates", ""]
    if data["action_candidates"]:
        for action in data["action_candidates"]:
            lines.append(f"- `{action['action_id']}` → `{action['command_hint']}` / execution=`{action['execution_allowed']}`")
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


def write_phase5_bridge_outputs(
    workspace: str | Path,
    *,
    phase4_package_path: str | Path | None = None,
    out_dir: str | Path | None = None,
) -> dict[str, Any]:
    workspace_path = Path(workspace)
    out_path = Path(out_dir) if out_dir else workspace_path
    out_path.mkdir(parents=True, exist_ok=True)

    report = build_phase5_domain_decision_bridge(
        workspace_path,
        phase4_package_path=phase4_package_path,
    )
    payload = report.to_dict()

    report_json = out_path / "PHASE5_DOMAIN_DECISION_BRIDGE.json"
    report_md = out_path / "PHASE5_DOMAIN_DECISION_BRIDGE.md"
    package_json = out_path / "PHASE5_DOMAIN_RULE_INPUT_PACKAGE.json"

    report_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    report_md.write_text(render_phase5_markdown(report), encoding="utf-8")
    package_json.write_text(
        json.dumps(report.domain_rule_input_package, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    return {
        "status": report.status,
        "workspace": str(workspace_path),
        "out_dir": str(out_path),
        "report_json": str(report_json),
        "report_md": str(report_md),
        "domain_rule_input_package": str(package_json),
        "warnings": report.warnings,
        "safety": report.safety,
    }
