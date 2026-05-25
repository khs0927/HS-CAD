from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PR62_CONTEXT = {
    "branch": "local/post-merge-local-validation-execution-pack",
    "pr_url": "https://github.com/khs0927/HS-CAD/pull/62",
    "base_branch": "design/final-live-runner-safety-spec-gate",
    "reported_validation": {
        "target": "tests/test_post_merge_local_validation_execution_pack.py: 4 passed",
        "compileall": "passed",
        "full_pytest": "passed",
        "ruff": "All checks passed",
        "cli_smoke": "hscad-post-merge-local-validation-pack passed",
    },
    "reported_safety": {
        "pr_validation_ran_local_validation": False,
        "cad_execution": False,
        "zwcad_com": False,
        "sendcommand": False,
        "xicad_alias_execution": False,
        "original_dwg_mutation": False,
        "final_live_runner_implemented": False,
        "outputs_committed": False,
        "dwg_dxf_committed": False,
    },
    "final_live_runner_gate": {
        "final_live_runner_implementation_allowed": False,
        "implementation_requires_separate_pr": True,
    },
}


MANUAL_LOCAL_VALIDATION_STEPS = [
    {
        "id": "operator-00-prerequisites",
        "title": "Manual prerequisites before running local validation",
        "status": "operator_required",
        "checklist": [
            "Human main merge decision is complete or explicit local validation approval exists.",
            "ZWCAD is installed and licensed on this Windows machine.",
            "The original DWG path is correct and will not be modified.",
            "The working copy DWG is a real copied file and differs from the original.",
            "The SaveAs target differs from both the original and working copy.",
            "C:/xicad exists if XiCAD policy validation is required.",
            "outputs/** remains uncommitted.",
            "Final live runner implementation is still not allowed.",
        ],
    },
    {
        "id": "operator-01-run-guarded-template",
        "title": "Run guarded PowerShell template manually",
        "status": "manual_only",
        "command": 'powershell -ExecutionPolicy Bypass -File outputs\\post_merge_local_validation_execution_pack\\RUN_LOCAL_VALIDATION_COMMANDS.template.ps1 -ConfirmRun',
        "checklist": [
            "Do not run without manually reading the generated script.",
            "Do not run if any path points original_dwg and working_copy_dwg to the same file.",
            "Do not run if save_as_target points to original_dwg.",
            "Stop immediately on unexpected ZWCAD behavior.",
        ],
    },
    {
        "id": "operator-02-fill-results",
        "title": "Fill LOCAL_01~04 result JSON files",
        "status": "manual_only",
        "result_files": [
            "outputs/local_validation_results/LOCAL_01_COPIED_DWG_SCAN_RESULT.json",
            "outputs/local_validation_results/LOCAL_02_COPIED_DWG_SAVEAS_RESULT.json",
            "outputs/local_validation_results/LOCAL_03_XICAD_POLICY_CANDIDATES_RESULT.json",
            "outputs/local_validation_results/LOCAL_04_PHASE12_CANDIDATE_GUARD_RESULT.json",
        ],
        "checklist": [
            "Set status to passed only when all pass conditions are true.",
            "Record original_hash_before and original_hash_after where applicable.",
            "Set sendcommand_used false for scan validation.",
            "Set execution_allowed false and sendcommand_allowed false for Phase 12 guard.",
            "Never edit these result files to force a pass without evidence.",
        ],
    },
    {
        "id": "operator-03-recheck-recorder",
        "title": "Run recorder and safety gate after result files are filled",
        "status": "manual_after_results",
        "commands": [
            "python -X utf8 -m src.main hscad-local-validation-recorder --repo-root . --result-dir outputs\\local_validation_results --out-dir outputs\\local_validation_recorder --create-templates false",
            "python -X utf8 -m src.main hscad-final-live-runner-safety-spec-gate --repo-root . --local-validation-summary-json outputs\\local_validation_recorder\\LOCAL_VALIDATION_RESULT_SUMMARY.json --out-dir outputs\\final_live_runner_safety_spec_gate",
        ],
        "checklist": [
            "LOCAL_VALIDATION_RESULT_SUMMARY.json must show all_local_validations_passed=true before safety spec review can proceed.",
            "Even if all passed, final live runner implementation remains a separate PR.",
        ],
    },
]


@dataclass(frozen=True)
class HandoffGate:
    id: str
    title: str
    status: str
    evidence: list[str] = field(default_factory=list)
    blocked_reasons: list[str] = field(default_factory=list)
    operator_action: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safety() -> dict[str, Any]:
    return {
        "this_package_runs_cad": False,
        "this_package_runs_powershell": False,
        "this_package_calls_zwcad_com": False,
        "this_package_calls_sendcommand": False,
        "this_package_executes_xicad_alias": False,
        "this_package_mutates_original_dwg": False,
        "this_package_implements_final_live_runner": False,
        "operator_manual_execution_required": True,
        "final_live_runner_implementation_allowed": False,
        "implementation_requires_separate_pr": True,
    }


def _path_warning(original_dwg: str, working_copy_dwg: str, save_as_target: str) -> list[str]:
    warnings: list[str] = []
    if original_dwg == working_copy_dwg:
        warnings.append("original_dwg equals working_copy_dwg")
    if original_dwg == save_as_target:
        warnings.append("original_dwg equals save_as_target")
    if working_copy_dwg == save_as_target:
        warnings.append("working_copy_dwg equals save_as_target")
    return warnings


def build_local_validation_operator_handoff(
    *,
    original_dwg: str = "C:/cad/test/original.dwg",
    working_copy_dwg: str = "C:/cad/test_work/copy.dwg",
    save_as_target: str = "C:/cad/test_work/result.dwg",
    xicad_root: str = "C:/xicad",
    command_pack_dir: str = "outputs/post_merge_local_validation_execution_pack",
    result_dir: str = "outputs/local_validation_results",
) -> dict[str, Any]:
    warnings = _path_warning(original_dwg, working_copy_dwg, save_as_target)
    gates = [
        HandoffGate(
            id="handoff-gate:path-separation",
            title="Original, working copy, and SaveAs paths are distinct",
            status="ok" if not warnings else "blocked",
            evidence=[
                f"original_dwg={original_dwg}",
                f"working_copy_dwg={working_copy_dwg}",
                f"save_as_target={save_as_target}",
            ],
            blocked_reasons=warnings,
            operator_action="Fix paths before running any local validation command.",
        ),
        HandoffGate(
            id="handoff-gate:pr62-safety-context",
            title="PR62 remained non-executing and implementation blocked",
            status="ok",
            evidence=[
                f"pr62={PR62_CONTEXT['pr_url']}",
                f"final_live_runner_implementation_allowed={PR62_CONTEXT['final_live_runner_gate']['final_live_runner_implementation_allowed']}",
            ],
            operator_action="Proceed only with manual local validation; do not implement runner.",
        ),
        HandoffGate(
            id="handoff-gate:manual-only",
            title="Local validation requires explicit human operator",
            status="operator_required",
            evidence=["PowerShell template requires -ConfirmRun", "outputs remain uncommitted"],
            operator_action="Human must inspect generated script and copied-DWG paths before execution.",
        ),
    ]

    status = "blocked" if warnings else "ready_for_manual_operator_validation"

    return {
        "task": "local_validation_operator_handoff",
        "generated_at": _now(),
        "status": status,
        "pr62_context": PR62_CONTEXT,
        "input_paths": {
            "original_dwg": original_dwg,
            "working_copy_dwg": working_copy_dwg,
            "save_as_target": save_as_target,
            "xicad_root": xicad_root,
            "command_pack_dir": command_pack_dir,
            "result_dir": result_dir,
        },
        "gates": [gate.to_dict() for gate in gates],
        "manual_local_validation_steps": MANUAL_LOCAL_VALIDATION_STEPS,
        "result_files_to_fill": MANUAL_LOCAL_VALIDATION_STEPS[2]["result_files"],
        "post_result_recheck_commands": MANUAL_LOCAL_VALIDATION_STEPS[3]["commands"],
        "final_live_runner_decision": {
            "implementation_allowed": False,
            "reason": "Manual local validation and safety spec review must complete; implementation requires a separate PR.",
        },
        "safety": _safety(),
    }


def render_handoff_markdown(package: dict[str, Any]) -> str:
    lines = [
        "# HS-CAD Local Validation Operator Handoff",
        "",
        f"- Status: `{package['status']}`",
        f"- PR #62: {package['pr62_context']['pr_url']}",
        f"- Final live runner implementation allowed: `{package['final_live_runner_decision']['implementation_allowed']}`",
        "",
        "## Gates",
        "",
    ]

    for gate in package["gates"]:
        lines.append(f"### {gate['id']}")
        lines.append(f"- Title: {gate['title']}")
        lines.append(f"- Status: `{gate['status']}`")
        if gate["blocked_reasons"]:
            lines.append(f"- Blocked: {', '.join(gate['blocked_reasons'])}")
        lines.append(f"- Operator action: {gate['operator_action']}")
        lines.append("")

    lines += ["## Manual Steps", ""]
    for step in package["manual_local_validation_steps"]:
        lines.append(f"### {step['id']} — {step['title']}")
        lines.append(f"- Status: `{step['status']}`")
        if "command" in step:
            lines.append("```powershell")
            lines.append(step["command"])
            lines.append("```")
        if "commands" in step:
            for command in step["commands"]:
                lines.append("```powershell")
                lines.append(command)
                lines.append("```")
        if "result_files" in step:
            lines.append("Result files:")
            for result_file in step["result_files"]:
                lines.append(f"- `{result_file}`")
        lines.append("Checklist:")
        for item in step["checklist"]:
            lines.append(f"- {item}")
        lines.append("")

    lines += ["## Safety", ""]
    for key, value in package["safety"].items():
        lines.append(f"- `{key}`: `{value}`")

    return "\n".join(lines).rstrip() + "\n"


def build_operator_prompt(package: dict[str, Any]) -> str:
    return f"""너는 HS-CAD Windows/ZWCAD 로컬 검증 오퍼레이터다.

목표:
PR #62에서 생성된 post-merge local validation execution pack을 사람이 직접 검토하고 필요 시 수동 실행한다.

중요:
이 프롬프트는 자동 실행 지시가 아니다.
먼저 original/copy/save-as 경로를 반드시 확인한다.
원본 DWG는 절대 수정하지 않는다.
final live runner는 구현하지 않는다.

현재 상태:
- PR #62: {package['pr62_context']['pr_url']}
- Handoff status: {package['status']}
- Final live runner implementation allowed: {package['final_live_runner_decision']['implementation_allowed']}

수동 실행 전 확인:
{chr(10).join(f"- {item}" for item in MANUAL_LOCAL_VALIDATION_STEPS[0]['checklist'])}

수동 실행 명령:
{MANUAL_LOCAL_VALIDATION_STEPS[1]['command']}

결과 파일 작성:
{chr(10).join(f"- {item}" for item in package['result_files_to_fill'])}

결과 작성 후 재검증:
{chr(10).join(f"- {item}" for item in package['post_result_recheck_commands'])}
"""


def write_operator_handoff_outputs(
    *,
    out_dir: str | Path = "outputs/local_validation_operator_handoff",
    original_dwg: str = "C:/cad/test/original.dwg",
    working_copy_dwg: str = "C:/cad/test_work/copy.dwg",
    save_as_target: str = "C:/cad/test_work/result.dwg",
    xicad_root: str = "C:/xicad",
) -> dict[str, Any]:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    package = build_local_validation_operator_handoff(
        original_dwg=original_dwg,
        working_copy_dwg=working_copy_dwg,
        save_as_target=save_as_target,
        xicad_root=xicad_root,
    )

    package_json = out / "LOCAL_VALIDATION_OPERATOR_HANDOFF.json"
    package_md = out / "LOCAL_VALIDATION_OPERATOR_HANDOFF.md"
    operator_prompt = out / "LOCAL_VALIDATION_OPERATOR_PROMPT.md"
    result_finalization = out / "RESULT_FINALIZATION_COMMANDS.json"

    package_json.write_text(json.dumps(package, ensure_ascii=False, indent=2), encoding="utf-8")
    package_md.write_text(render_handoff_markdown(package), encoding="utf-8")
    operator_prompt.write_text(build_operator_prompt(package), encoding="utf-8")
    result_finalization.write_text(
        json.dumps(
            {
                "result_files_to_fill": package["result_files_to_fill"],
                "post_result_recheck_commands": package["post_result_recheck_commands"],
                "final_live_runner_decision": package["final_live_runner_decision"],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    return {
        "status": package["status"],
        "out_dir": str(out),
        "package_json": str(package_json),
        "package_md": str(package_md),
        "operator_prompt": str(operator_prompt),
        "result_finalization": str(result_finalization),
        "safety": package["safety"],
    }
