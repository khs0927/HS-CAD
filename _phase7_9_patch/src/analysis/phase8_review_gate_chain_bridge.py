from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_PHASE7_PACKAGE = "PHASE7_DOMAIN_DECISION_PACKAGE.json"


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
        "review_gate_required": True,
        "signoff_required": True,
        "safe_execution_mode": "dry_run_only",
    }


def build_phase8_review_gate_chain(
    workspace: str | Path,
    *,
    phase7_package_path: str | Path | None = None,
) -> dict[str, Any]:
    workspace_path = Path(workspace)
    input_path = Path(phase7_package_path) if phase7_package_path else workspace_path / DEFAULT_PHASE7_PACKAGE
    warnings: list[str] = []

    if not input_path.exists():
        warnings.append(f"Phase7 decision package missing: {input_path}")
        decisions: list[dict[str, Any]] = []
        status = "blocked"
    else:
        data = json.loads(input_path.read_text(encoding="utf-8"))
        decisions = data.get("decisions") or []
        status = "ready_for_review" if any(item.get("status") != "blocked" for item in decisions) else "blocked"

    command_plan_steps: list[dict[str, Any]] = []
    review_gate_items: list[dict[str, Any]] = []
    signoff_items: list[dict[str, Any]] = []

    for idx, decision in enumerate(decisions, start=1):
        candidate = decision.get("command_plan_candidate") or {}
        blocked = decision.get("status") == "blocked" or decision.get("blocked_reasons")
        step = {
            "step_id": f"phase8:dry-run-step:{idx}",
            "source_decision_id": decision.get("decision_id"),
            "status": "blocked" if blocked else "review_required",
            "command_type": candidate.get("command_type") or "domain-rule-review-only",
            "command_hint": candidate.get("command_hint") or "domain-rule-command-plan --review-only",
            "execution_allowed": False,
            "review_required": True,
            "blocked_reasons": decision.get("blocked_reasons") or [],
        }
        command_plan_steps.append(step)
        review_gate_items.append(
            {
                "gate_id": f"phase8:review-gate:{idx}",
                "source_step_id": step["step_id"],
                "status": "blocked" if blocked else "needs_human_review",
                "required_checks": [
                    "evidence_refs_verified",
                    "execution_allowed_false",
                    "no_sendcommand",
                    "no_original_dwg_mutation",
                ],
            }
        )
        signoff_items.append(
            {
                "signoff_id": f"phase8:signoff:{idx}",
                "source_step_id": step["step_id"],
                "operator_approved": False,
                "execution_allowed": False,
                "status": "not_approved",
            }
        )

    if not decisions:
        warnings.append("No decisions were available to build command plan/review gate chain.")

    if any(item["status"] == "blocked" for item in command_plan_steps) and any(item["status"] != "blocked" for item in command_plan_steps):
        status = "partial"

    package = {
        "task": "phase8_review_gate_chain_bridge",
        "workspace": str(workspace_path),
        "generated_at": _now(),
        "status": status,
        "source_phase7_package": str(input_path),
        "command_plan": {
            "mode": "dry_run_only",
            "dry_run_steps": command_plan_steps,
            "execution_allowed": False,
        },
        "review_gate": {
            "status": status,
            "items": review_gate_items,
            "human_review_required": True,
        },
        "signoff_manifest": {
            "status": "not_approved",
            "items": signoff_items,
            "operator_approved": False,
            "execution_allowed": False,
        },
        "safe_execution_stub": {
            "status": "dry_run_only",
            "mutation_allowed": False,
            "sendcommand_allowed": False,
            "copy_execution_allowed": False,
        },
        "warnings": warnings,
        "safety": _safety(),
    }
    return package


def render_phase8_markdown(package: dict[str, Any]) -> str:
    lines = [
        "# HS-CAD Phase 8 Review Gate Chain Bridge",
        "",
        f"- Workspace: `{package['workspace']}`",
        f"- Status: `{package['status']}`",
        f"- Source Phase 7 package: `{package['source_phase7_package']}`",
        "",
        "## Dry-run Steps",
        "",
    ]
    for step in package["command_plan"]["dry_run_steps"]:
        lines.append(f"- `{step['step_id']}` | status=`{step['status']}` | execution=`{step['execution_allowed']}`")

    lines += ["", "## Safety", ""]
    for key, value in package["safety"].items():
        lines.append(f"- `{key}`: `{value}`")
    return "\n".join(lines).rstrip() + "\n"


def write_phase8_outputs(
    workspace: str | Path,
    *,
    phase7_package_path: str | Path | None = None,
    out_dir: str | Path | None = None,
) -> dict[str, Any]:
    workspace_path = Path(workspace)
    out_path = Path(out_dir) if out_dir else workspace_path
    out_path.mkdir(parents=True, exist_ok=True)

    package = build_phase8_review_gate_chain(workspace_path, phase7_package_path=phase7_package_path)

    files = {
        "PHASE8_REVIEW_GATE_CHAIN.json": package,
        "PHASE8_COMMAND_PLAN.json": package["command_plan"],
        "PHASE8_REVIEW_GATE.json": package["review_gate"],
        "PHASE8_SIGNOFF_MANIFEST.json": package["signoff_manifest"],
        "PHASE8_SAFE_EXECUTION_STUB.json": package["safe_execution_stub"],
    }
    written: dict[str, str] = {}
    for name, payload in files.items():
        path = out_path / name
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        written[name] = str(path)

    md = out_path / "PHASE8_REVIEW_GATE_CHAIN.md"
    md.write_text(render_phase8_markdown(package), encoding="utf-8")
    written[md.name] = str(md)

    return {
        "status": package["status"],
        "workspace": str(workspace_path),
        "out_dir": str(out_path),
        "artifacts": written,
        "warnings": package["warnings"],
        "safety": package["safety"],
    }
