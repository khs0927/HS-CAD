from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from .autopilot_policy import classify_autopilot_command
from .autopilot_report import write_autopilot_outputs


@dataclass(frozen=True)
class AutopilotStep:
    name: str
    command: str
    reason: str
    args: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def infer_autopilot_mode(task: str, *, mode: str = "auto", has_image: bool = False, has_dwg: bool = False) -> str:
    if mode and mode != "auto":
        return mode
    text = task.lower()
    if "contract" in text or "계약" in text or "검증" in text or "wal" in text or "d1" in text:
        return "contract"
    if has_image or "이미지" in text or "스캔" in text or "dxf" in text or "도면화" in text:
        return "floorplan"
    if has_dwg or "dwg" in text or "레이어" in text or "블록" in text:
        return "dwg_review"
    return "general"


def build_autopilot_steps(
    task: str,
    *,
    mode: str = "auto",
    aliases: str = "WAL,D1,W1,INS,COL,BE",
    out_dir: str | Path = "outputs/autopilot",
    has_image: bool = False,
    has_dwg: bool = False,
    synthetic: bool = False,
) -> list[AutopilotStep]:
    selected_mode = infer_autopilot_mode(task, mode=mode, has_image=has_image, has_dwg=has_dwg)
    out = Path(out_dir)
    steps: list[AutopilotStep] = []

    steps.append(AutopilotStep("tool_plan", "hscad-tool-plan", "Create an ordered HS-CAD workflow plan.", {"task": task, "out_dir": str(out / "tool_plan")}))

    if selected_mode == "contract":
        steps.extend([
            AutopilotStep("contract_plan", "xicad-contract-plan", "Create XiCAD contract verification plan.", {"aliases": aliases, "out_dir": str(out / "contracts")}),
            AutopilotStep("review_matrix", "xicad-contract-review-matrix", "Create contract review matrix.", {"aliases": aliases, "out_dir": str(out / "sessions")}),
        ])
        first_alias = aliases.split(",")[0].strip() if aliases else "WAL"
        steps.append(AutopilotStep("first_session", "xicad-contract-session", "Create first manual verification session.", {"alias": first_alias, "out_dir": str(out / "sessions")}))
    elif selected_mode == "floorplan":
        if synthetic:
            steps.append(AutopilotStep("floorplan_synthetic", "python -X utf8 -m neuro_seq_cad.app.cli analyze --synthetic", "Run synthetic floorplan pipeline.", {"out_dir": str(out / "floorplan"), "xicad_plan": True}))
        else:
            steps.append(AutopilotStep("floorplan_plan_only", "floorplan-analyze", "Floorplan analyze requires an image path; held if no image.", {"out_dir": str(out / "floorplan")}))
        steps.append(AutopilotStep("xicad_plan_generate", "xicad-plan-generate", "Generate XiCAD command plan from floorplan outputs.", {"result_dir": str(out / "floorplan")}))
    elif selected_mode == "dwg_review":
        steps.extend([
            AutopilotStep("dwg_scan", "scan", "Read-only DWG object scan.", {}),
            AutopilotStep("layer_counts", "layers", "Read-only layer counts.", {}),
            AutopilotStep("block_counts", "blocks", "Read-only block counts.", {}),
            AutopilotStep("architecture_audit", "analyze-architecture", "Read-only architecture audit.", {}),
        ])
    else:
        steps.append(AutopilotStep("check_tools", "hscad-check-tools", "Check HS-CAD tool availability.", {"out_dir": str(out / "tool_check")}))

    return steps


def _safe_call_step(step: AutopilotStep) -> dict[str, Any]:
    """Run internal safe actions when possible.

    This avoids shell execution. Unknown or unavailable integrations are reported
    instead of raising hard failures.
    """
    try:
        if step.command == "xicad-contract-plan":
            from src.orchestrator.xicad_contract_test_plan import create_contract_test_plan
            paths = create_contract_test_plan(step.args.get("aliases", "WAL,D1,W1"), step.args.get("out_dir", "outputs/xicad_contracts"))
            return {"name": step.name, "status": "ok", "output": paths}

        if step.command == "xicad-contract-review-matrix":
            from src.orchestrator.xicad_contract_workbench import write_review_matrix
            paths = write_review_matrix(step.args.get("aliases", "WAL,D1,W1"), step.args.get("out_dir", "outputs/xicad_sessions"))
            return {"name": step.name, "status": "ok", "output": paths}

        if step.command == "xicad-contract-session":
            from src.orchestrator.xicad_contract_workbench import write_contract_session
            paths = write_contract_session(step.args.get("alias", "WAL"), step.args.get("out_dir", "outputs/xicad_sessions"))
            return {"name": step.name, "status": "ok", "output": paths}

        if step.command == "xicad-plan-generate":
            from neuro_seq_cad.app.xicad_plan_cli_support import generate_xicad_plan_outputs
            paths = generate_xicad_plan_outputs(step.args.get("result_dir", "output"))
            return {"name": step.name, "status": "ok", "output": paths}

        if step.command == "hscad-tool-plan":
            from src.orchestrator.workflow_planner import plan_hscad_workflow, write_plan_files
            plan = plan_hscad_workflow(step.args.get("task", ""))
            paths = write_plan_files(plan, step.args.get("out_dir", "outputs/tool_plan"))
            return {"name": step.name, "status": "ok", "output": paths}

        # Synthetic floorplan is safe in principle, but project signatures vary.
        # Keep it held unless the local project wires a direct safe runner.
        if "neuro_seq_cad" in step.command:
            return {"name": step.name, "status": "held", "output": "Synthetic neuro_seq_cad run should be invoked by local CLI integration."}

        return {"name": step.name, "status": "skipped", "output": "No internal safe runner registered for this step."}
    except Exception as exc:
        return {"name": step.name, "status": "error", "output": str(exc)}


def run_autopilot(
    task: str,
    *,
    mode: str = "auto",
    aliases: str = "WAL,D1,W1,INS,COL,BE",
    out_dir: str | Path = "outputs/autopilot",
    has_image: bool = False,
    has_dwg: bool = False,
    synthetic: bool = False,
    run_safe: bool = False,
) -> dict[str, Any]:
    selected_mode = infer_autopilot_mode(task, mode=mode, has_image=has_image, has_dwg=has_dwg)
    steps = build_autopilot_steps(task, mode=selected_mode, aliases=aliases, out_dir=out_dir, has_image=has_image, has_dwg=has_dwg, synthetic=synthetic)

    plan_steps = []
    executed = []
    held = []
    warnings = []

    for step in steps:
        decision = classify_autopilot_command(step.command)
        plan_steps.append({**step.to_dict(), "decision": decision.to_dict()})
        if decision.can_run and run_safe:
            result = _safe_call_step(step)
            if result.get("status") == "held":
                held.append({"name": step.name, "reason": result.get("output", "")})
            else:
                executed.append(result)
        else:
            held.append({"name": step.name, "reason": decision.reason})

    payload = {
        "task": task,
        "mode": selected_mode,
        "run_safe": run_safe,
        "plan": {"steps": plan_steps},
        "executed_steps": executed,
        "held_steps": held,
        "warnings": warnings,
    }
    paths = write_autopilot_outputs(payload, out_dir)
    payload["outputs"] = paths
    # rewrite result with output paths included
    write_autopilot_outputs(payload, out_dir)
    return payload
