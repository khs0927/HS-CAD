from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

BLOCKED = "blocked"
READY = "ready_for_human_review"


@dataclass(frozen=True)
class ExecutionCandidatePlannerInput:
    preflight_decision_json: str | Path = "outputs/final_live_runner_preflight_guard/FINAL_LIVE_RUNNER_PREFLIGHT_DECISION.json"
    manual_copy_interface_json: str | Path = "outputs/final_live_runner_manual_copy_only_interface/FINAL_LIVE_RUNNER_MANUAL_COPY_ONLY_INTERFACE.json"
    oda_conversion_contract_json: str | Path = "outputs/oda_conversion_contract/ODA_CONVERSION_CONTRACT.json"
    operator_approved: bool = False
    manual_live_flag: bool = False
    operator_name: str = "human-reviewer"


@dataclass(frozen=True)
class PlannerDecision:
    task: str = "execution_candidate_planner"
    status: str = BLOCKED
    generated_at: str = ""
    execution_candidate_allowed: bool = False
    sendcommand_allowed: bool = False
    saveas_allowed: bool = False
    original_dwg_mutation_allowed: bool = False
    xicad_alias_execution_allowed: bool = False
    production_execution_allowed: bool = False
    blocked_reasons: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    candidate_steps_for_human_review: list[dict[str, Any]] = field(default_factory=list)
    rollback_requirements: list[str] = field(default_factory=list)
    audit_requirements: list[str] = field(default_factory=list)
    evidence_summary: dict[str, Any] = field(default_factory=dict)
    safety: dict[str, bool] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _path(value: str | Path) -> Path:
    return value if isinstance(value, Path) else Path(value)


def _load_json(path: str | Path) -> tuple[dict[str, Any], str]:
    p = _path(path)
    if not p.exists():
        return {}, f"missing:{p}"
    try:
        payload = json.loads(p.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        return {}, f"invalid_json:{p}:{exc}"
    if not isinstance(payload, dict):
        return {}, f"invalid_json_root:{p}"
    return payload, ""


def _safety() -> dict[str, bool]:
    return {
        "this_package_runs_cad": False,
        "this_package_changes_drawings": False,
        "this_package_performs_live_action": False,
        "this_package_uses_cad_command_channel": False,
        "this_package_uses_save_operation": False,
        "this_package_uses_xicad_action": False,
        "this_package_implements_production_runner": False,
        "default_execution_candidate_allowed": False,
    }


def _true(payload: dict[str, Any], key: str) -> bool:
    return payload.get(key) is True


def evaluate_execution_candidate_plan(inp: ExecutionCandidatePlannerInput) -> dict[str, Any]:
    blocked: list[str] = []
    warnings: list[str] = []
    preflight, preflight_err = _load_json(inp.preflight_decision_json)
    manual, manual_err = _load_json(inp.manual_copy_interface_json)
    oda, oda_err = _load_json(inp.oda_conversion_contract_json)

    if preflight_err:
        blocked.append(f"preflight_decision_json:{preflight_err}")
    if manual_err:
        blocked.append(f"manual_copy_interface_json:{manual_err}")
    if oda_err:
        blocked.append(f"oda_conversion_contract_json:{oda_err}")

    if preflight:
        if preflight.get("status") != "ready_for_manual_implementation_review":
            blocked.append(f"preflight status is not ready: {preflight.get('status')!r}")
        for key in ["execution_allowed", "sendcommand_allowed", "saveas_allowed", "original_dwg_mutation_allowed", "xicad_alias_execution_allowed", "final_live_runner_implemented"]:
            if _true(preflight, key):
                blocked.append(f"preflight unsafe flag true: {key}")

    if manual:
        if manual.get("status") != "ready_for_operator_review":
            blocked.append(f"manual copy-only interface status is not ready: {manual.get('status')!r}")
        for key in ["execution_allowed", "sendcommand_allowed", "saveas_allowed", "original_dwg_mutation_allowed", "xicad_alias_execution_allowed", "production_execution_allowed"]:
            if _true(manual, key):
                blocked.append(f"manual interface unsafe flag true: {key}")

    if oda:
        if oda.get("status") != "converted":
            blocked.append(f"ODA contract status is not converted: {oda.get('status')!r}")
        if oda.get("original_mutated") is not False:
            blocked.append("ODA contract does not prove original_mutated=false")
        if not oda.get("converted_dxf_path"):
            warnings.append("ODA converted_dxf_path is missing")
        if not oda.get("log_path"):
            warnings.append("ODA log_path is missing")

    if not inp.operator_approved:
        blocked.append("operator_approved is false")
    if not inp.manual_live_flag:
        blocked.append("manual_live_flag is false")

    status = READY if not blocked else BLOCKED
    steps = []
    if status == READY:
        steps = [
            {"id": "review-only-step-01", "title": "Human reviews preflight, manual-copy, and ODA evidence", "performs_live_action": False},
            {"id": "review-only-step-02", "title": "Human confirms rollback and audit requirements", "performs_live_action": False},
            {"id": "review-only-step-03", "title": "A separate future PR may propose a copy-only action candidate", "performs_live_action": False},
        ]

    return PlannerDecision(
        status=status,
        generated_at=_now(),
        blocked_reasons=blocked,
        warnings=warnings,
        candidate_steps_for_human_review=steps,
        rollback_requirements=["Keep the original DWG untouched.", "Keep working copy and result paths distinct.", "Preserve all evidence JSON files for review."],
        audit_requirements=["Record preflight decision path.", "Record manual-copy interface path.", "Record ODA contract path.", "Record that this planner performed no live drawing action."],
        evidence_summary={"preflight_decision_json": str(inp.preflight_decision_json), "manual_copy_interface_json": str(inp.manual_copy_interface_json), "oda_conversion_contract_json": str(inp.oda_conversion_contract_json), "preflight_status": preflight.get("status") if preflight else None, "manual_copy_status": manual.get("status") if manual else None, "oda_status": oda.get("status") if oda else None, "operator_approved": inp.operator_approved, "manual_live_flag": inp.manual_live_flag, "operator_name": inp.operator_name},
        safety=_safety(),
    ).to_dict()


def render_markdown(decision: dict[str, Any]) -> str:
    lines = ["# HS-CAD Execution Candidate Planner", "", f"- Status: `{decision['status']}`", f"- Execution candidate allowed: `{decision['execution_candidate_allowed']}`", f"- SendCommand allowed: `{decision['sendcommand_allowed']}`", f"- SaveAs allowed: `{decision['saveas_allowed']}`", f"- Original DWG mutation allowed: `{decision['original_dwg_mutation_allowed']}`", f"- XiCAD alias execution allowed: `{decision['xicad_alias_execution_allowed']}`", f"- Production execution allowed: `{decision['production_execution_allowed']}`", "", "## Blocked reasons"]
    lines.extend([f"- {item}" for item in decision["blocked_reasons"]] or ["- None"])
    lines += ["", "## Candidate steps for human review"]
    if decision["candidate_steps_for_human_review"]:
        for step in decision["candidate_steps_for_human_review"]:
            lines.append(f"- `{step['id']}`: {step['title']} (performs_live_action={step['performs_live_action']})")
    else:
        lines.append("- None")
    return "\n".join(lines).rstrip() + "\n"


def write_execution_candidate_planner_outputs(inp: ExecutionCandidatePlannerInput, *, out_dir: str | Path = "outputs/execution_candidate_planner") -> dict[str, Any]:
    out = _path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    decision = evaluate_execution_candidate_plan(inp)
    decision_json = out / "EXECUTION_CANDIDATE_PLANNER_DECISION.json"
    decision_md = out / "EXECUTION_CANDIDATE_PLANNER_DECISION.md"
    candidate_steps_json = out / "EXECUTION_CANDIDATE_STEPS_FOR_HUMAN_REVIEW.json"
    rollback_json = out / "EXECUTION_CANDIDATE_ROLLBACK_REQUIREMENTS.json"
    audit_json = out / "EXECUTION_CANDIDATE_AUDIT_REQUIREMENTS.json"
    refusal_json = out / "EXECUTION_CANDIDATE_REFUSAL_REASONS.json"
    decision_json.write_text(json.dumps(decision, ensure_ascii=False, indent=2), encoding="utf-8")
    decision_md.write_text(render_markdown(decision), encoding="utf-8")
    candidate_steps_json.write_text(json.dumps(decision["candidate_steps_for_human_review"], ensure_ascii=False, indent=2), encoding="utf-8")
    rollback_json.write_text(json.dumps(decision["rollback_requirements"], ensure_ascii=False, indent=2), encoding="utf-8")
    audit_json.write_text(json.dumps(decision["audit_requirements"], ensure_ascii=False, indent=2), encoding="utf-8")
    refusal_json.write_text(json.dumps(decision["blocked_reasons"], ensure_ascii=False, indent=2), encoding="utf-8")
    return {"status": decision["status"], "out_dir": str(out), "decision_json": str(decision_json), "decision_md": str(decision_md), "candidate_steps_json": str(candidate_steps_json), "rollback_json": str(rollback_json), "audit_json": str(audit_json), "refusal_json": str(refusal_json), "execution_candidate_allowed": False, "sendcommand_allowed": False, "saveas_allowed": False, "original_dwg_mutation_allowed": False, "xicad_alias_execution_allowed": False, "production_execution_allowed": False}
