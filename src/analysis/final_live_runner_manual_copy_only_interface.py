from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

BLOCKED = "blocked"
READY = "ready_for_operator_review"


@dataclass(frozen=True)
class ManualCopyOnlyInput:
    preflight_decision_json: str | Path = "outputs/final_live_runner_preflight_guard/FINAL_LIVE_RUNNER_PREFLIGHT_DECISION.json"
    audit_intent_json: str | Path = "outputs/final_live_runner_preflight_guard/FINAL_LIVE_RUNNER_PREFLIGHT_AUDIT_INTENT.json"
    refusal_reasons_json: str | Path = "outputs/final_live_runner_preflight_guard/FINAL_LIVE_RUNNER_PREFLIGHT_REFUSAL_REASONS.json"
    next_plan_json: str | Path = "outputs/final_live_runner_preflight_guard/NEXT_IMPLEMENTATION_PR_PLAN.json"
    original_dwg: str | Path = "C:/cad/test/original.dwg"
    working_copy_dwg: str | Path = "C:/cad/test_work/copy.dwg"
    save_as_target: str | Path = "C:/cad/test_work/result.dwg"
    operator_name: str = "human-reviewer"
    manual_live_flag: bool = False
    operator_approved: bool = False


@dataclass(frozen=True)
class ManualCopyOnlyDecision:
    task: str = "final_live_runner_manual_copy_only_interface"
    status: str = BLOCKED
    generated_at: str = ""
    execution_allowed: bool = False
    sendcommand_allowed: bool = False
    saveas_allowed: bool = False
    xicad_alias_execution_allowed: bool = False
    original_dwg_mutation_allowed: bool = False
    production_execution_allowed: bool = False
    final_live_runner_implemented: bool = False
    operator_review_required: bool = True
    blocked_reasons: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    operator_prompt: str = ""
    audit_intent: dict[str, Any] = field(default_factory=dict)
    evidence_summary: dict[str, Any] = field(default_factory=dict)
    next_actions: list[str] = field(default_factory=list)
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
        value = json.loads(p.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        return {}, f"invalid_json:{p}:{exc}"
    if not isinstance(value, dict):
        return {}, f"invalid_json_root:{p}"
    return value, ""


def _safe_flags() -> dict[str, bool]:
    return {
        "this_package_runs_cad": False,
        "this_package_opens_dwg": False,
        "this_package_calls_sendcommand": False,
        "this_package_calls_saveas": False,
        "this_package_executes_xicad_alias": False,
        "this_package_mutates_original_dwg": False,
        "this_package_implements_production_runner": False,
        "default_execution_allowed": False,
    }


def _operator_prompt(inp: ManualCopyOnlyInput, status: str, blocked: list[str]) -> str:
    lines = [
        "# HS-CAD Final Live Runner Manual Copy-only Operator Prompt",
        "",
        "This interface is review-only. It does not execute CAD, SendCommand, SaveAs, or XiCAD aliases.",
        "",
        f"- Status: `{status}`",
        f"- Operator: `{inp.operator_name}`",
        f"- Original DWG: `{inp.original_dwg}`",
        f"- Working copy DWG: `{inp.working_copy_dwg}`",
        f"- SaveAs target: `{inp.save_as_target}`",
        "",
        "## Safety defaults",
        "- execution_allowed: false",
        "- sendcommand_allowed: false",
        "- saveas_allowed: false",
        "- xicad_alias_execution_allowed: false",
        "- original_dwg_mutation_allowed: false",
        "- production_execution_allowed: false",
        "",
    ]
    if blocked:
        lines.append("## Refusal reasons")
        for reason in blocked:
            lines.append(f"- {reason}")
    else:
        lines += [
            "## Human review checklist",
            "- Confirm the preflight decision is ready_for_manual_implementation_review.",
            "- Confirm the original DWG and working copy paths are distinct.",
            "- Confirm no execution is performed by this interface.",
            "- Confirm a separate PR is required before any execution candidate.",
        ]
    return "\n".join(lines).rstrip() + "\n"


def evaluate_manual_copy_only_interface(inp: ManualCopyOnlyInput) -> dict[str, Any]:
    blocked: list[str] = []
    warnings: list[str] = []

    preflight, preflight_err = _load_json(inp.preflight_decision_json)
    audit, audit_err = _load_json(inp.audit_intent_json)
    refusals, refusal_err = _load_json(inp.refusal_reasons_json)
    next_plan, next_err = _load_json(inp.next_plan_json)

    if preflight_err:
        blocked.append(f"preflight_decision_json:{preflight_err}")
    if audit_err:
        warnings.append(f"audit_intent_json:{audit_err}")
        audit = {}
    if refusal_err:
        warnings.append(f"refusal_reasons_json:{refusal_err}")
        refusals = {}
    if next_err:
        warnings.append(f"next_plan_json:{next_err}")
        next_plan = {}

    if preflight:
        if preflight.get("status") != "ready_for_manual_implementation_review":
            blocked.append(f"preflight status is not ready: {preflight.get('status')!r}")
        for key in [
            "execution_allowed",
            "sendcommand_allowed",
            "saveas_allowed",
            "xicad_alias_execution_allowed",
            "original_dwg_mutation_allowed",
            "final_live_runner_implemented",
        ]:
            if preflight.get(key) is True:
                blocked.append(f"preflight unsafe flag true: {key}")

    if not inp.operator_approved:
        blocked.append("operator_approved is false")
    if not inp.manual_live_flag:
        blocked.append("manual_live_flag is false")

    if str(_path(inp.original_dwg)).lower() == str(_path(inp.working_copy_dwg)).lower():
        blocked.append("original_dwg and working_copy_dwg are identical")
    if str(_path(inp.save_as_target)).lower() in {
        str(_path(inp.original_dwg)).lower(),
        str(_path(inp.working_copy_dwg)).lower(),
    }:
        blocked.append("save_as_target must be distinct from original and working copy")

    status = READY if not blocked else BLOCKED
    prompt = _operator_prompt(inp, status, blocked)

    decision = ManualCopyOnlyDecision(
        status=status,
        generated_at=_now(),
        blocked_reasons=blocked,
        warnings=warnings,
        operator_prompt=prompt,
        audit_intent={
            "source": str(inp.audit_intent_json),
            "preflight_audit_intent": audit,
            "manual_copy_only_interface": True,
            "will_open_dwg": False,
            "will_saveas": False,
            "will_sendcommand": False,
            "will_execute_xicad_alias": False,
            "will_mutate_original": False,
            "operator_approved": inp.operator_approved,
            "manual_live_flag": inp.manual_live_flag,
        },
        evidence_summary={
            "preflight_decision_json": str(inp.preflight_decision_json),
            "audit_intent_json": str(inp.audit_intent_json),
            "refusal_reasons_json": str(inp.refusal_reasons_json),
            "next_plan_json": str(inp.next_plan_json),
            "preflight_status": preflight.get("status") if preflight else None,
            "preflight_refusals": refusals,
            "next_plan": next_plan,
            "original_dwg": str(inp.original_dwg),
            "working_copy_dwg": str(inp.working_copy_dwg),
            "save_as_target": str(inp.save_as_target),
        },
        next_actions=[
            "If blocked, rerun preflight guard and fix refusal reasons.",
            "If ready_for_operator_review, create a separate execution-candidate PR only after human approval.",
            "Do not execute SendCommand, SaveAs, or XiCAD aliases in this interface PR.",
        ],
        safety=_safe_flags(),
    )
    return decision.to_dict()


def render_markdown(decision: dict[str, Any]) -> str:
    lines = [
        "# HS-CAD Final Live Runner Manual Copy-only Interface",
        "",
        f"- Status: `{decision['status']}`",
        f"- Execution allowed: `{decision['execution_allowed']}`",
        f"- SendCommand allowed: `{decision['sendcommand_allowed']}`",
        f"- SaveAs allowed: `{decision['saveas_allowed']}`",
        f"- XiCAD alias execution allowed: `{decision['xicad_alias_execution_allowed']}`",
        f"- Original DWG mutation allowed: `{decision['original_dwg_mutation_allowed']}`",
        f"- Production execution allowed: `{decision['production_execution_allowed']}`",
        "",
        "## Blocked reasons",
    ]
    if decision["blocked_reasons"]:
        lines += [f"- {item}" for item in decision["blocked_reasons"]]
    else:
        lines.append("- None")
    lines += ["", "## Safety"]
    for key, value in decision["safety"].items():
        lines.append(f"- `{key}`: `{value}`")
    lines += ["", "## Next actions"]
    for item in decision["next_actions"]:
        lines.append(f"- {item}")
    return "\n".join(lines).rstrip() + "\n"


def write_manual_copy_only_interface_outputs(
    inp: ManualCopyOnlyInput,
    *,
    out_dir: str | Path = "outputs/final_live_runner_manual_copy_only_interface",
) -> dict[str, Any]:
    out = _path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    decision = evaluate_manual_copy_only_interface(inp)

    files = {
        "interface_json": out / "FINAL_LIVE_RUNNER_MANUAL_COPY_ONLY_INTERFACE.json",
        "interface_md": out / "FINAL_LIVE_RUNNER_MANUAL_COPY_ONLY_INTERFACE.md",
        "operator_prompt_md": out / "FINAL_LIVE_RUNNER_OPERATOR_CONFIRMATION_PROMPT.md",
        "audit_intent_json": out / "FINAL_LIVE_RUNNER_MANUAL_COPY_ONLY_AUDIT_INTENT.json",
        "refusal_json": out / "FINAL_LIVE_RUNNER_MANUAL_COPY_ONLY_REFUSAL.json",
        "next_pr_json": out / "NEXT_MANUAL_COPY_ONLY_EXECUTION_CANDIDATE_PR.json",
    }
    files["interface_json"].write_text(json.dumps(decision, ensure_ascii=False, indent=2), encoding="utf-8")
    files["interface_md"].write_text(render_markdown(decision), encoding="utf-8")
    files["operator_prompt_md"].write_text(decision["operator_prompt"], encoding="utf-8")
    files["audit_intent_json"].write_text(json.dumps(decision["audit_intent"], ensure_ascii=False, indent=2), encoding="utf-8")
    files["refusal_json"].write_text(json.dumps(decision["blocked_reasons"], ensure_ascii=False, indent=2), encoding="utf-8")
    files["next_pr_json"].write_text(
        json.dumps(
            {
                "recommended_next_pr": "feat/final-live-runner-manual-copy-only-execution-candidate",
                "can_start": False,
                "reason": "Execution candidate requires separate human approval even when this interface is ready.",
                "disallowed_in_current_pr": ["SendCommand", "SaveAs", "XiCAD alias execution", "original DWG mutation"],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return {
        "status": decision["status"],
        "out_dir": str(out),
        **{key: str(value) for key, value in files.items()},
        "execution_allowed": False,
        "sendcommand_allowed": False,
        "saveas_allowed": False,
        "xicad_alias_execution_allowed": False,
        "original_dwg_mutation_allowed": False,
        "production_execution_allowed": False,
    }
