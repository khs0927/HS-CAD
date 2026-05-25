from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_PHASE8_CHAIN = "PHASE8_REVIEW_GATE_CHAIN.json"
DEFAULT_PHASE9_SUMMARY = "PHASE9_PIPELINE_READINESS_SUMMARY.json"


@dataclass(frozen=True)
class Phase10ConnectorDecision:
    decision_id: str
    source_step_id: str
    status: str
    title: str
    reason: str
    command_hint: str
    review_required: bool = True
    execution_allowed: bool = False
    required_checks: list[str] = field(default_factory=list)
    blocked_reasons: list[str] = field(default_factory=list)

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
        "copied_dwg_validation_only": True,
        "live_execution_allowed": False,
    }


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def build_phase10_domain_decision_connector(
    workspace: str | Path,
    *,
    phase8_chain_path: str | Path | None = None,
    phase9_summary_path: str | Path | None = None,
) -> dict[str, Any]:
    workspace_path = Path(workspace)
    phase8_path = Path(phase8_chain_path) if phase8_chain_path else workspace_path / DEFAULT_PHASE8_CHAIN
    phase9_path = Path(phase9_summary_path) if phase9_summary_path else workspace_path / DEFAULT_PHASE9_SUMMARY

    warnings: list[str] = []
    decisions: list[Phase10ConnectorDecision] = []

    if not phase8_path.exists():
        warnings.append(f"Phase8 review gate chain missing: {phase8_path}")
    else:
        phase8 = _load_json(phase8_path)
        dry_run_steps = ((phase8.get("command_plan") or {}).get("dry_run_steps") or [])
        review_items = {str(item.get("source_step_id") or ""): item for item in ((phase8.get("review_gate") or {}).get("items") or [])}

        for idx, step in enumerate(dry_run_steps, start=1):
            step_id = str(step.get("step_id") or f"phase8:step:{idx}")
            blocked = step.get("status") == "blocked" or bool(step.get("blocked_reasons"))
            review_item = review_items.get(step_id, {})
            decisions.append(
                Phase10ConnectorDecision(
                    decision_id=f"phase10:domain-decision:{idx}",
                    source_step_id=step_id,
                    status="blocked" if blocked else "ready_for_domain_review",
                    title=f"Domain review candidate from {step_id}",
                    reason="Mapped from Phase 8 review-gated dry-run step.",
                    command_hint=str(step.get("command_hint") or "domain-rule-decision --review-only"),
                    review_required=True,
                    execution_allowed=False,
                    required_checks=[str(item) for item in (review_item.get("required_checks") or [])],
                    blocked_reasons=[str(item) for item in (step.get("blocked_reasons") or [])],
                )
            )

    pipeline_readiness = "unknown"
    if phase9_path.exists():
        phase9 = _load_json(phase9_path)
        pipeline_readiness = str(phase9.get("status") or "unknown")
    else:
        warnings.append(f"Phase9 readiness summary missing: {phase9_path}")

    if not decisions:
        decisions.append(
            Phase10ConnectorDecision(
                decision_id="phase10:domain-decision:no-input",
                source_step_id="phase8:missing",
                status="blocked",
                title="No Phase 8 dry-run steps available",
                reason="Phase10 cannot connect to Domain Rule Decision without Phase8 review chain.",
                command_hint="domain-rule-decision --review-only",
                blocked_reasons=["missing_phase8_review_chain"],
            )
        )

    status = "ready_for_domain_review" if any(item.status != "blocked" for item in decisions) else "blocked"
    if any(item.status == "blocked" for item in decisions) and status != "blocked":
        status = "partial"

    package = {
        "task": "phase10_domain_decision_connector",
        "workspace": str(workspace_path),
        "generated_at": _now(),
        "status": status,
        "pipeline_readiness": pipeline_readiness,
        "source_phase8_chain": str(phase8_path),
        "source_phase9_summary": str(phase9_path),
        "domain_decision_candidates": [item.to_dict() for item in decisions],
        "domain_rule_decision_cli_plan": {
            "mode": "review_only",
            "recommended_cli": "domain-rule-decision",
            "execution_allowed": False,
            "sendcommand_allowed": False,
            "operator_approved": False,
            "notes": [
                "This package only prepares inputs for review-only Domain Rule Decision.",
                "Do not run command execution from this package.",
            ],
        },
        "review_checklist": [
            "Confirm Phase8 review gate exists.",
            "Confirm Phase9 readiness is not blocked.",
            "Confirm every decision candidate has execution_allowed=false.",
            "Confirm Domain Rule Decision is run in review-only mode.",
        ],
        "warnings": warnings,
        "safety": _safety(),
    }
    return package


def render_phase10_markdown(package: dict[str, Any]) -> str:
    lines = [
        "# HS-CAD Phase 10 Domain Decision Connector",
        "",
        f"- Workspace: `{package['workspace']}`",
        f"- Status: `{package['status']}`",
        f"- Pipeline readiness: `{package['pipeline_readiness']}`",
        "",
        "## Domain Decision Candidates",
        "",
    ]
    for item in package["domain_decision_candidates"]:
        lines.append(
            f"- `{item['decision_id']}` | status=`{item['status']}` | source=`{item['source_step_id']}` | execution=`{item['execution_allowed']}`"
        )
        if item["blocked_reasons"]:
            lines.append(f"  - blocked: {', '.join(item['blocked_reasons'])}")

    lines += ["", "## Safety", ""]
    for key, value in package["safety"].items():
        lines.append(f"- `{key}`: `{value}`")

    if package["warnings"]:
        lines += ["", "## Warnings", ""]
        lines.extend(f"- {warning}" for warning in package["warnings"])

    return "\n".join(lines).rstrip() + "\n"


def write_phase10_outputs(
    workspace: str | Path,
    *,
    phase8_chain_path: str | Path | None = None,
    phase9_summary_path: str | Path | None = None,
    out_dir: str | Path | None = None,
) -> dict[str, Any]:
    workspace_path = Path(workspace)
    out_path = Path(out_dir) if out_dir else workspace_path
    out_path.mkdir(parents=True, exist_ok=True)

    package = build_phase10_domain_decision_connector(
        workspace_path,
        phase8_chain_path=phase8_chain_path,
        phase9_summary_path=phase9_summary_path,
    )

    json_path = out_path / "PHASE10_DOMAIN_DECISION_CONNECTOR.json"
    md_path = out_path / "PHASE10_DOMAIN_DECISION_CONNECTOR.md"
    cli_plan_path = out_path / "PHASE10_DOMAIN_RULE_DECISION_CLI_PLAN.json"

    json_path.write_text(json.dumps(package, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(render_phase10_markdown(package), encoding="utf-8")
    cli_plan_path.write_text(
        json.dumps(package["domain_rule_decision_cli_plan"], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    return {
        "status": package["status"],
        "workspace": str(workspace_path),
        "out_dir": str(out_path),
        "connector_json": str(json_path),
        "connector_md": str(md_path),
        "cli_plan_json": str(cli_plan_path),
        "warnings": package["warnings"],
        "safety": package["safety"],
    }
