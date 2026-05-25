from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PR61_CONTEXT = {
    "branch": "design/final-live-runner-safety-spec-gate",
    "pr_url": "https://github.com/khs0927/HS-CAD/pull/61",
    "base_branch": "local/post-main-validation-recorder-final-runner-spec",
    "reported_validation": {
        "target": "tests/test_final_live_runner_safety_spec_gate.py: 4 passed",
        "compileall": "passed",
        "full_pytest": "235 passed, 16 skipped",
        "ruff": "All checks passed",
        "cli_smoke": "src.main --help and hscad-final-live-runner-safety-spec-gate passed",
    },
    "gate_status": {
        "local_validation_summary_exists": False,
        "all_local_validations_passed": False,
        "safety_spec_docs_exist": True,
        "status": "blocked",
        "blocked_is_expected": True,
    },
    "final_live_runner_decision": {
        "safety_spec_pr_can_be_reviewed": True,
        "implementation_pr_can_start": False,
        "implementation_requires_separate_pr": True,
    },
    "remaining_todo": [
        "PR #55~#59 human approval and main merge decision",
        "post-main local validation manual execution",
        "LOCAL_VALIDATION_RESULT_SUMMARY all passed",
        "safety spec PR review",
        "final live runner implementation PR only after all prerequisites",
    ],
}


LOCAL_VALIDATION_STEPS = [
    {
        "id": "local-01-copied-dwg-scan",
        "title": "Copied DWG scan validation",
        "command_template": 'python -X utf8 -m src.main zwcad-copy-scan-validate --original-dwg "{original_dwg}" --working-copy-dwg "{working_copy_dwg}" --out-dir outputs/zwcad_copy_validation_live',
        "result_file": "LOCAL_01_COPIED_DWG_SCAN_RESULT.json",
        "environment": "Windows + ZWCAD installed",
        "required_confirmations": [
            "original_hash_before recorded",
            "original_hash_after equals original_hash_before",
            "working_copy_dwg differs from original_dwg",
            "audit log written",
            "sendcommand_used is false",
        ],
        "pass_conditions": {
            "original_hash_unchanged": True,
            "working_copy_differs_from_original": True,
            "audit_log_written": True,
            "sendcommand_used": False,
            "status": "passed",
        },
    },
    {
        "id": "local-02-copied-dwg-saveas",
        "title": "Copied DWG SaveAs validation",
        "command_template": 'python -X utf8 -m src.main zwcad-copy-saveas-validate --original-dwg "{original_dwg}" --working-copy-dwg "{working_copy_dwg}" --save-as-target "{save_as_target}" --out-dir outputs/zwcad_copy_saveas_validation_live --overwrite-copy',
        "result_file": "LOCAL_02_COPIED_DWG_SAVEAS_RESULT.json",
        "environment": "Windows + ZWCAD installed",
        "required_confirmations": [
            "save_as_target differs from original_dwg",
            "original_hash_after equals original_hash_before",
            "before scan artifact written",
            "after scan artifact written",
            "delta report written",
            "audit log written",
        ],
        "pass_conditions": {
            "save_as_target_differs_from_original": True,
            "original_hash_unchanged": True,
            "before_scan_written": True,
            "after_scan_written": True,
            "delta_report_written": True,
            "audit_log_written": True,
            "status": "passed",
        },
    },
    {
        "id": "local-03-xicad-policy-candidates",
        "title": "C:/xicad allowlist policy validation",
        "command_template": 'python -X utf8 -m src.main xicad-policy-candidates --xicad-root "{xicad_root}" --out-dir outputs/xicad_policy_candidates_verify',
        "result_file": "LOCAL_03_XICAD_POLICY_CANDIDATES_RESULT.json",
        "environment": "Windows + C:/xicad",
        "required_confirmations": [
            "allowed_for_execution is false",
            "execution_allowed_aliases is empty list",
            "unknown aliases are blocked",
            "destructive aliases are blocked",
            "policy artifacts written",
        ],
        "pass_conditions": {
            "allowed_for_execution": False,
            "execution_allowed_aliases": [],
            "unknown_aliases_blocked": True,
            "destructive_aliases_blocked": True,
            "policy_artifacts_written": True,
            "status": "passed",
        },
    },
    {
        "id": "local-04-phase12-candidate-guard",
        "title": "Phase 12 manual candidate guard only",
        "command_template": 'python -X utf8 -m src.main hscad-analysis-phase12-manual-live-candidate --workspace "{phase12_workspace}" --alias "{alias}" --manual-live-flag --operator-approved --out-dir outputs/phase12_manual_live_candidate_verify',
        "result_file": "LOCAL_04_PHASE12_CANDIDATE_GUARD_RESULT.json",
        "environment": "Windows + copied DWG + allowlist artifacts",
        "required_confirmations": [
            "candidate created or blocked with reason",
            "execution_allowed is false",
            "sendcommand_allowed is false",
            "final_runner_implemented is false",
            "original_dwg_mutated is false",
        ],
        "pass_conditions": {
            "candidate_created_or_blocked_with_reason": True,
            "execution_allowed": False,
            "sendcommand_allowed": False,
            "final_runner_implemented": False,
            "original_dwg_mutated": False,
            "status": "passed",
        },
    },
]


@dataclass(frozen=True)
class LocalExecutionGate:
    id: str
    title: str
    status: str
    evidence: list[str] = field(default_factory=list)
    blocked_reasons: list[str] = field(default_factory=list)
    next_action: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_bool(value: Any) -> bool:
    return bool(value) is True


def _safety() -> dict[str, Any]:
    return {
        "this_package_runs_cad": False,
        "this_package_calls_zwcad_com": False,
        "this_package_calls_sendcommand": False,
        "this_package_executes_xicad_alias": False,
        "this_package_mutates_original_dwg": False,
        "this_package_implements_final_live_runner": False,
        "local_execution_requires_explicit_operator": True,
        "copied_dwg_only": True,
        "final_live_runner_implementation_allowed": False,
    }


def _render_command(template: str, values: dict[str, str]) -> str:
    safe = {
        "original_dwg": values.get("original_dwg", "C:/cad/test/original.dwg"),
        "working_copy_dwg": values.get("working_copy_dwg", "C:/cad/test_work/copy.dwg"),
        "save_as_target": values.get("save_as_target", "C:/cad/test_work/result.dwg"),
        "xicad_root": values.get("xicad_root", "C:/xicad"),
        "phase12_workspace": values.get("phase12_workspace", "outputs/phase10_11_domain_copy_verify"),
        "alias": values.get("alias", "WAL"),
    }
    return template.format(**safe)


def build_post_merge_local_validation_execution_pack(
    *,
    original_dwg: str = "C:/cad/test/original.dwg",
    working_copy_dwg: str = "C:/cad/test_work/copy.dwg",
    save_as_target: str = "C:/cad/test_work/result.dwg",
    xicad_root: str = "C:/xicad",
    phase12_workspace: str = "outputs/phase10_11_domain_copy_verify",
    alias: str = "WAL",
) -> dict[str, Any]:
    values = {
        "original_dwg": original_dwg,
        "working_copy_dwg": working_copy_dwg,
        "save_as_target": save_as_target,
        "xicad_root": xicad_root,
        "phase12_workspace": phase12_workspace,
        "alias": alias,
    }

    gates: list[LocalExecutionGate] = []
    path_warnings: list[str] = []

    if original_dwg == working_copy_dwg:
        path_warnings.append("original_dwg and working_copy_dwg are identical")
    if original_dwg == save_as_target:
        path_warnings.append("original_dwg and save_as_target are identical")
    if working_copy_dwg == save_as_target:
        path_warnings.append("working_copy_dwg and save_as_target are identical")

    gates.append(
        LocalExecutionGate(
            id="gate:path-separation",
            title="Original/copy/save-as paths are distinct",
            status="ok" if not path_warnings else "blocked",
            evidence=[f"original_dwg={original_dwg}", f"working_copy_dwg={working_copy_dwg}", f"save_as_target={save_as_target}"],
            blocked_reasons=path_warnings,
            next_action="Fix path separation before any local validation command is run.",
        )
    )

    gates.append(
        LocalExecutionGate(
            id="gate:pr61-blocked-is-expected",
            title="PR61 safety gate blocked implementation as expected",
            status="ok" if PR61_CONTEXT["gate_status"]["blocked_is_expected"] else "blocked",
            evidence=[
                f"gate_status={PR61_CONTEXT['gate_status']['status']}",
                f"implementation_pr_can_start={PR61_CONTEXT['final_live_runner_decision']['implementation_pr_can_start']}",
            ],
            next_action="Proceed only to local validation, not implementation.",
        )
    )

    commands = []
    for step in LOCAL_VALIDATION_STEPS:
        commands.append(
            {
                **step,
                "rendered_command": _render_command(step["command_template"], values),
            }
        )

    return {
        "task": "post_merge_local_validation_execution_pack",
        "generated_at": _now(),
        "status": "ready_for_manual_local_validation" if not path_warnings else "blocked",
        "pr61_context": PR61_CONTEXT,
        "input_paths": values,
        "gates": [gate.to_dict() for gate in gates],
        "local_validation_steps": commands,
        "result_files_to_fill": [step["result_file"] for step in LOCAL_VALIDATION_STEPS],
        "after_manual_execution_commands": [
            "python -X utf8 -m src.main hscad-local-validation-recorder --repo-root . --result-dir outputs\\local_validation_results --out-dir outputs\\local_validation_recorder --create-templates false",
            "python -X utf8 -m src.main hscad-final-live-runner-safety-spec-gate --repo-root . --local-validation-summary-json outputs\\local_validation_recorder\\LOCAL_VALIDATION_RESULT_SUMMARY.json --out-dir outputs\\final_live_runner_safety_spec_gate",
        ],
        "final_live_runner_state": {
            "implementation_allowed": False,
            "reason": "Local validation summary must be all passed and safety spec must be reviewed; implementation still requires a separate PR.",
        },
        "safety": _safety(),
    }


def render_markdown(pack: dict[str, Any]) -> str:
    lines = [
        "# HS-CAD Post-merge Local Validation Execution Pack",
        "",
        f"- Status: `{pack['status']}`",
        f"- PR #61: {pack['pr61_context']['pr_url']}",
        f"- PR61 reported full pytest: `{pack['pr61_context']['reported_validation']['full_pytest']}`",
        f"- Final live runner implementation allowed: `{pack['final_live_runner_state']['implementation_allowed']}`",
        "",
        "## Gates",
        "",
    ]

    for gate in pack["gates"]:
        lines.append(f"### {gate['id']}")
        lines.append(f"- Title: {gate['title']}")
        lines.append(f"- Status: `{gate['status']}`")
        if gate["blocked_reasons"]:
            lines.append(f"- Blocked: {', '.join(gate['blocked_reasons'])}")
        lines.append(f"- Next: {gate['next_action']}")
        lines.append("")

    lines += ["## Manual Local Validation Commands", ""]
    for step in pack["local_validation_steps"]:
        lines.append(f"### {step['id']} — {step['title']}")
        lines.append(f"- Environment: {step['environment']}")
        lines.append(f"- Result file: `{step['result_file']}`")
        lines.append("```powershell")
        lines.append(step["rendered_command"])
        lines.append("```")
        lines.append("Confirm:")
        for item in step["required_confirmations"]:
            lines.append(f"- {item}")
        lines.append("")

    lines += ["## After Manual Execution", ""]
    for cmd in pack["after_manual_execution_commands"]:
        lines.append("```powershell")
        lines.append(cmd)
        lines.append("```")

    lines += ["", "## Safety", ""]
    for key, value in pack["safety"].items():
        lines.append(f"- `{key}`: `{value}`")

    return "\n".join(lines).rstrip() + "\n"


def build_result_template(step_id: str) -> dict[str, Any]:
    step = next((item for item in LOCAL_VALIDATION_STEPS if item["id"] == step_id), None)
    if step is None:
        raise ValueError(f"Unknown local validation step: {step_id}")

    template: dict[str, Any] = {
        "id": step["id"],
        "title": step["title"],
        "status": "pending",
        "notes": "Fill this result after manual execution. Keep outputs uncommitted.",
    }
    for key, expected in step["pass_conditions"].items():
        template[key] = None
    return template


def write_post_merge_local_validation_execution_outputs(
    *,
    out_dir: str | Path = "outputs/post_merge_local_validation_execution_pack",
    result_template_dir: str | Path = "outputs/local_validation_results",
    original_dwg: str = "C:/cad/test/original.dwg",
    working_copy_dwg: str = "C:/cad/test_work/copy.dwg",
    save_as_target: str = "C:/cad/test_work/result.dwg",
    xicad_root: str = "C:/xicad",
    phase12_workspace: str = "outputs/phase10_11_domain_copy_verify",
    alias: str = "WAL",
) -> dict[str, Any]:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    result_dir = Path(result_template_dir)
    result_dir.mkdir(parents=True, exist_ok=True)

    pack = build_post_merge_local_validation_execution_pack(
        original_dwg=original_dwg,
        working_copy_dwg=working_copy_dwg,
        save_as_target=save_as_target,
        xicad_root=xicad_root,
        phase12_workspace=phase12_workspace,
        alias=alias,
    )

    pack_json = out / "POST_MERGE_LOCAL_VALIDATION_EXECUTION_PACK.json"
    pack_md = out / "POST_MERGE_LOCAL_VALIDATION_EXECUTION_PACK.md"
    command_ps1 = out / "RUN_LOCAL_VALIDATION_COMMANDS.template.ps1"
    result_schema_json = out / "LOCAL_VALIDATION_RESULT_SCHEMA.json"

    pack_json.write_text(json.dumps(pack, ensure_ascii=False, indent=2), encoding="utf-8")
    pack_md.write_text(render_markdown(pack), encoding="utf-8")
    result_schema_json.write_text(json.dumps(LOCAL_VALIDATION_STEPS, ensure_ascii=False, indent=2), encoding="utf-8")

    ps_lines = [
        "param(",
        "  [switch]$ConfirmRun",
        ")",
        'if (-not $ConfirmRun) { Write-Host "Refusing to run. Re-run with -ConfirmRun after verifying copied DWG paths."; exit 1 }',
        'Write-Host "Running HS-CAD local validation commands. Ensure original DWG is never modified."',
    ]
    for step in pack["local_validation_steps"]:
        ps_lines.append(f'Write-Host "STEP {step["id"]}: {step["title"]}"')
        ps_lines.append(step["rendered_command"])
    command_ps1.write_text("\n".join(ps_lines) + "\n", encoding="utf-8")

    templates: dict[str, str] = {}
    for step in LOCAL_VALIDATION_STEPS:
        path = result_dir / step["result_file"]
        path.write_text(json.dumps(build_result_template(step["id"]), ensure_ascii=False, indent=2), encoding="utf-8")
        templates[step["id"]] = str(path)

    return {
        "status": pack["status"],
        "out_dir": str(out),
        "result_template_dir": str(result_dir),
        "pack_json": str(pack_json),
        "pack_md": str(pack_md),
        "command_template_ps1": str(command_ps1),
        "result_schema_json": str(result_schema_json),
        "result_templates": templates,
        "safety": pack["safety"],
    }
