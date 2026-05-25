from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_PHASE6_INPUT = "DOMAIN_RULE_DECISION_INPUT_FROM_PHASE6.json"


@dataclass(frozen=True)
class Phase7Decision:
    decision_id: str
    source_finding_id: str
    status: str
    title: str
    reason: str
    required_evidence: list[str] = field(default_factory=list)
    blocked_reasons: list[str] = field(default_factory=list)
    command_plan_candidate: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


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


def build_phase7_domain_decision_package(
    workspace: str | Path,
    *,
    phase6_input_path: str | Path | None = None,
) -> dict[str, Any]:
    workspace_path = Path(workspace)
    input_path = Path(phase6_input_path) if phase6_input_path else workspace_path / DEFAULT_PHASE6_INPUT
    warnings: list[str] = []
    decisions: list[Phase7Decision] = []

    if not input_path.exists():
        warnings.append(f"Phase6 Domain Rule Decision input missing: {input_path}")
        decisions.append(
            Phase7Decision(
                decision_id="phase7:decision:missing-phase6-input",
                source_finding_id="phase6:missing",
                status="blocked",
                title="Missing Phase 6 Domain Rule Decision input",
                reason="DOMAIN_RULE_DECISION_INPUT_FROM_PHASE6.json was not found.",
                required_evidence=[DEFAULT_PHASE6_INPUT],
                blocked_reasons=["missing_phase6_domain_rule_decision_input"],
            )
        )
    else:
        data = json.loads(input_path.read_text(encoding="utf-8"))
        findings = data.get("findings") or []
        review_actions = data.get("review_actions") or []
        actions_by_finding = {str(item.get("source_finding_id") or ""): item for item in review_actions}

        for idx, finding in enumerate(findings, start=1):
            finding_id = str(finding.get("id") or f"phase6:finding:{idx}")
            blocked = [str(item) for item in (finding.get("blocked_reasons") or [])]
            action = actions_by_finding.get(finding_id, {})
            status = "blocked" if blocked or finding.get("status") == "blocked" else "ready_for_review"

            decisions.append(
                Phase7Decision(
                    decision_id=f"phase7:decision:{idx}",
                    source_finding_id=finding_id,
                    status=status,
                    title=str(finding.get("title") or f"Phase7 decision {idx}"),
                    reason=str(finding.get("reason") or ""),
                    required_evidence=[str(item) for item in (finding.get("evidence_refs") or action.get("required_evidence") or [])],
                    blocked_reasons=blocked,
                    command_plan_candidate={
                        "candidate_id": f"phase7:command-plan-candidate:{idx}",
                        "source_decision_id": f"phase7:decision:{idx}",
                        "status": "blocked" if status == "blocked" else "review_required",
                        "command_type": "domain-rule-review-only",
                        "command_hint": str(action.get("command_hint") or "domain-rule-command-plan --review-only"),
                        "execution_allowed": False,
                        "review_required": True,
                    },
                )
            )

        if not decisions:
            warnings.append("Phase6 input exists but no findings were present.")
            decisions.append(
                Phase7Decision(
                    decision_id="phase7:decision:no-findings",
                    source_finding_id="phase6:none",
                    status="blocked",
                    title="No normalized findings",
                    reason="Phase6 input contains no findings.",
                    blocked_reasons=["empty_phase6_findings"],
                )
            )

    status = "ready_for_review" if any(item.status != "blocked" for item in decisions) else "blocked"
    if any(item.status == "blocked" for item in decisions) and status == "ready_for_review":
        status = "partial"

    return {
        "task": "phase7_domain_decision_package_bridge",
        "workspace": str(workspace_path),
        "generated_at": _now(),
        "status": status,
        "source_phase6_input": str(input_path),
        "decisions": [item.to_dict() for item in decisions],
        "blocked_reasons": sorted({reason for item in decisions for reason in item.blocked_reasons}),
        "required_evidence": sorted({ev for item in decisions for ev in item.required_evidence}),
        "review_checklist": [
            "Confirm all decisions are review-only.",
            "Confirm command_plan_candidate.execution_allowed is false.",
            "Confirm blocked decisions do not produce executable plans.",
            "Confirm evidence refs exist before running Domain Rule review.",
        ],
        "warnings": warnings,
        "safety": _safety(),
    }


def render_phase7_markdown(package: dict[str, Any]) -> str:
    lines = [
        "# HS-CAD Phase 7 Domain Decision Package Bridge",
        "",
        f"- Workspace: `{package['workspace']}`",
        f"- Status: `{package['status']}`",
        f"- Source Phase 6 input: `{package['source_phase6_input']}`",
        "",
        "## Decisions",
        "",
    ]
    for item in package["decisions"]:
        lines.append(f"- `{item['decision_id']}` | status=`{item['status']}` | {item['title']}")
        if item["blocked_reasons"]:
            lines.append(f"  - blocked: {', '.join(item['blocked_reasons'])}")

    lines += ["", "## Safety", ""]
    for key, value in package["safety"].items():
        lines.append(f"- `{key}`: `{value}`")
    return "\n".join(lines).rstrip() + "\n"


def write_phase7_outputs(
    workspace: str | Path,
    *,
    phase6_input_path: str | Path | None = None,
    out_dir: str | Path | None = None,
) -> dict[str, Any]:
    workspace_path = Path(workspace)
    out_path = Path(out_dir) if out_dir else workspace_path
    out_path.mkdir(parents=True, exist_ok=True)

    package = build_phase7_domain_decision_package(workspace_path, phase6_input_path=phase6_input_path)
    report_json = out_path / "PHASE7_DOMAIN_DECISION_PACKAGE.json"
    report_md = out_path / "PHASE7_DOMAIN_DECISION_PACKAGE.md"

    report_json.write_text(json.dumps(package, ensure_ascii=False, indent=2), encoding="utf-8")
    report_md.write_text(render_phase7_markdown(package), encoding="utf-8")

    return {
        "status": package["status"],
        "workspace": str(workspace_path),
        "out_dir": str(out_path),
        "package_json": str(report_json),
        "package_md": str(report_md),
        "warnings": package["warnings"],
        "safety": package["safety"],
    }
