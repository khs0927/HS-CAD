from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PR56_CONTEXT = {
    "branch": "integration/main-ready-review-only-pipeline",
    "pr_url": "https://github.com/khs0927/HS-CAD/pull/56",
    "title": "Validate PR55 main-ready review-only integration",
    "source_branch": "origin/integration/main-merge-readiness-decision",
    "base_branch": "main",
    "merge_result": "no conflicts, --no-ff merge commit created",
    "reported_validation": {
        "helper_targeted_test": "3 passed",
        "full_pytest": "206 passed, 16 skipped",
        "compileall": "passed",
        "src_main_help": "passed",
        "helper_cli": "hscad-pr55-main-ready-validation passed",
        "ruff": "skipped locally because ruff was not installed in that environment",
    },
    "reported_decision": "main-ready yes",
    "reported_safety": {
        "main_direct_push_allowed": False,
        "actual_main_merge_performed": False,
        "cad_execution_allowed": False,
        "zwcad_com_sendcommand_allowed": False,
        "xicad_alias_execution_allowed": False,
        "domain_rule_command_execution_allowed": False,
        "copied_dwg_live_validation_allowed": False,
        "final_live_runner_implemented": False,
        "final_live_runner_allowed": False,
        "review_only_pipeline_only": True,
    },
}

FINAL_MAIN_REVIEW_REQUIRED_COMMANDS = [
    "python -X utf8 -m compileall -q src tests",
    "python -X utf8 -m pytest -q",
    "python -X utf8 -m src.main --help",
    "python -X utf8 -m src.main hscad-main-merge-readiness-decision --out-dir outputs/main_merge_operator_review_decision",
    "python -X utf8 -m src.main hscad-pr55-main-ready-validation --repo-root . --out-dir outputs/pr55_main_ready_review_only_validation",
]

OPTIONAL_RUFF_COMMAND = "python -X utf8 -m ruff check src tests --select E9,F63,F7,F82,F821"

POST_MERGE_LOCAL_VALIDATION_COMMANDS = [
    {
        "id": "local-01-copied-dwg-scan",
        "title": "Copied DWG scan validation",
        "command": 'python -X utf8 -m src.main zwcad-copy-scan-validate --original-dwg "C:/cad/test/original.dwg" --working-copy-dwg "C:/cad/test_work/copy.dwg" --out-dir outputs/zwcad_copy_validation_live',
        "environment": "Windows + ZWCAD installed",
        "status": "manual_only_after_main_merge",
        "confirm": [
            "original_dwg_hash_before_recorded",
            "original_dwg_hash_after_unchanged",
            "working_copy_path_differs_from_original",
            "audit_log_written",
            "no_sendcommand_for_scan",
        ],
    },
    {
        "id": "local-02-copied-dwg-saveas",
        "title": "Copied DWG SaveAs validation",
        "command": 'python -X utf8 -m src.main zwcad-copy-saveas-validate --original-dwg "C:/cad/test/original.dwg" --working-copy-dwg "C:/cad/test_work/copy.dwg" --save-as-target "C:/cad/test_work/result.dwg" --out-dir outputs/zwcad_copy_saveas_validation_live --overwrite-copy',
        "environment": "Windows + ZWCAD installed",
        "status": "manual_only_after_main_merge",
        "confirm": [
            "save_as_target_differs_from_original",
            "original_dwg_hash_after_unchanged",
            "before_scan_written",
            "after_scan_written",
            "delta_report_written",
            "audit_log_written",
        ],
    },
    {
        "id": "local-03-xicad-policy-candidates",
        "title": "C:/xicad policy candidate validation",
        "command": 'python -X utf8 -m src.main xicad-policy-candidates --xicad-root C:/xicad --out-dir outputs/xicad_policy_candidates_verify',
        "environment": "Windows + local C:/xicad",
        "status": "manual_only_after_main_merge",
        "confirm": [
            "allowed_for_execution_false",
            "execution_allowed_aliases_empty",
            "unknown_aliases_blocked",
            "destructive_aliases_blocked",
            "policy_artifacts_written",
        ],
    },
    {
        "id": "local-04-phase12-candidate-guard",
        "title": "Phase 12 manual candidate guard only",
        "command": "python -X utf8 -m src.main hscad-analysis-phase12-manual-live-candidate --workspace outputs/phase10_11_domain_copy_verify --alias WAL --manual-live-flag --operator-approved --out-dir outputs/phase12_manual_live_candidate_verify",
        "environment": "Windows + copied DWG + allowlist artifacts",
        "status": "manual_only_after_main_merge",
        "confirm": [
            "candidate_created_or_blocked_with_reason",
            "execution_allowed_false",
            "sendcommand_allowed_false",
            "final_runner_guard_not_implemented",
            "original_dwg_not_mutated",
        ],
    },
]


@dataclass(frozen=True)
class OperatorGate:
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
        "main_direct_push_allowed": False,
        "auto_merge_allowed": False,
        "operator_review_required": True,
        "source_mutation_allowed": False,
        "original_dwg_mutation_allowed": False,
        "cad_execution_allowed_by_default": False,
        "zwcad_com_sendcommand_allowed": False,
        "xicad_alias_execution_allowed": False,
        "domain_rule_command_execution_allowed": False,
        "copied_dwg_live_validation_allowed_in_this_step": False,
        "final_live_runner_implemented": False,
        "final_live_runner_allowed": False,
        "post_merge_local_validation_manual_only": True,
    }


def build_main_merge_operator_review(
    repo_root: str | Path = ".",
    *,
    pr56_workspace: str | Path = "outputs/pr55_main_ready_review_only_validation",
) -> dict[str, Any]:
    repo = Path(repo_root)
    workspace = Path(pr56_workspace)

    gates: list[OperatorGate] = []

    pr56_report = workspace / "PR55_MAIN_READY_REVIEW_ONLY_VALIDATION.json"
    pr56_checklist = workspace / "PR55_MAIN_READY_CHECKLIST.json"

    gates.append(
        OperatorGate(
            id="operator-gate:pr56-artifacts",
            title="PR #56 validation artifacts exist",
            status="ok" if pr56_report.exists() and pr56_checklist.exists() else "review_required",
            evidence=[str(p) for p in [pr56_report, pr56_checklist] if p.exists()],
            blocked_reasons=[] if pr56_report.exists() and pr56_checklist.exists() else ["pr56_outputs_not_found_in_workspace"],
            operator_action="If artifacts are missing locally, rerun hscad-pr55-main-ready-validation.",
        )
    )

    unsafe_reported_flags = [
        key for key, value in PR56_CONTEXT["reported_safety"].items()
        if key != "review_only_pipeline_only" and value is True
    ]
    if PR56_CONTEXT["reported_safety"].get("review_only_pipeline_only") is not True:
        unsafe_reported_flags.append("review_only_pipeline_only_not_true")

    gates.append(
        OperatorGate(
            id="operator-gate:reported-safety",
            title="PR #56 reported safety flags are conservative",
            status="ok" if not unsafe_reported_flags else "blocked",
            evidence=[f"{k}={v}" for k, v in PR56_CONTEXT["reported_safety"].items()],
            blocked_reasons=[f"unsafe:{flag}" for flag in unsafe_reported_flags],
            operator_action="Do not merge if any execution-related flag is true.",
        )
    )

    gates.append(
        OperatorGate(
            id="operator-gate:required-local-validation-policy",
            title="Local-only ZWCAD/XiCAD validation stays post-merge/manual",
            status="ok",
            evidence=[item["id"] for item in POST_MERGE_LOCAL_VALIDATION_COMMANDS],
            operator_action="Do not run local-only validation in the main merge PR. Keep it post-merge/manual.",
        )
    )

    status = "ready_for_operator_main_merge_review"
    if any(g.status == "blocked" for g in gates):
        status = "blocked"
    elif any(g.status == "review_required" for g in gates):
        status = "review_required"

    return {
        "task": "main_merge_operator_review",
        "generated_at": _now(),
        "repo_root": str(repo),
        "pr56_workspace": str(workspace),
        "status": status,
        "pr56_context": PR56_CONTEXT,
        "operator_gates": [gate.to_dict() for gate in gates],
        "final_pre_merge_validation_commands": FINAL_MAIN_REVIEW_REQUIRED_COMMANDS,
        "optional_ruff_command": OPTIONAL_RUFF_COMMAND,
        "main_merge_allowed_scope": [
            "review-only analysis pipeline",
            "plan-only Domain Rule bridge",
            "copied-DWG validation planning",
            "manual live candidate guard",
            "safety policy docs",
            "main-ready review-only validation helper",
        ],
        "main_merge_disallowed_scope": [
            "final live runner",
            "ZWCAD COM SendCommand execution",
            "XiCAD alias execution",
            "Domain Rule Command Plan execution",
            "copied-DWG live validation",
            "original DWG mutation",
            "automatic operator approval",
        ],
        "post_merge_local_validation_commands": POST_MERGE_LOCAL_VALIDATION_COMMANDS,
        "operator_main_merge_checklist": [
            "Review PR #56 diff manually.",
            "Confirm no outputs/scratch/DWG/DXF/ZIP/cache files are committed.",
            "Confirm full pytest still passes on the PR branch.",
            "Confirm src.main --help still passes.",
            "Confirm final live runner is not implemented.",
            "Confirm SendCommand and XiCAD alias execution are not enabled.",
            "Merge only review-only/plan-only/safety-guard scope to main.",
            "After merge, run local-only ZWCAD/XiCAD validation manually on copied DWG only.",
        ],
        "safety": _safety(),
    }


def render_operator_review_markdown(package: dict[str, Any]) -> str:
    lines = [
        "# HS-CAD Main Merge Operator Review Package",
        "",
        "## Summary",
        "",
        f"- Status: `{package['status']}`",
        f"- PR #56: {package['pr56_context']['pr_url']}",
        f"- Branch: `{package['pr56_context']['branch']}`",
        f"- Reported full pytest: `{package['pr56_context']['reported_validation']['full_pytest']}`",
        "",
        "## Operator Gates",
        "",
    ]

    for gate in package["operator_gates"]:
        lines.append(f"### {gate['id']}")
        lines.append("")
        lines.append(f"- Title: {gate['title']}")
        lines.append(f"- Status: `{gate['status']}`")
        if gate["blocked_reasons"]:
            lines.append(f"- Blocked reasons: {', '.join(gate['blocked_reasons'])}")
        lines.append(f"- Operator action: {gate['operator_action']}")
        lines.append("")

    lines += ["## Final Pre-merge Validation Commands", ""]
    for cmd in package["final_pre_merge_validation_commands"]:
        lines.append("```powershell")
        lines.append(cmd)
        lines.append("```")

    lines += ["", "## Optional Ruff Command", ""]
    lines.append("```powershell")
    lines.append(package["optional_ruff_command"])
    lines.append("```")

    lines += ["", "## Allowed in Main Merge", ""]
    lines.extend(f"- {item}" for item in package["main_merge_allowed_scope"])

    lines += ["", "## Disallowed in Main Merge", ""]
    lines.extend(f"- {item}" for item in package["main_merge_disallowed_scope"])

    lines += ["", "## Post-merge Local-only Validation", ""]
    for step in package["post_merge_local_validation_commands"]:
        lines.append(f"### {step['id']}")
        lines.append("")
        lines.append(f"- Title: {step['title']}")
        lines.append(f"- Environment: {step['environment']}")
        lines.append(f"- Status: `{step['status']}`")
        lines.append("```powershell")
        lines.append(step["command"])
        lines.append("```")

    lines += ["", "## Safety", ""]
    for key, value in package["safety"].items():
        lines.append(f"- `{key}`: `{value}`")

    return "\n".join(lines).rstrip() + "\n"


def build_main_merge_operator_prompt(package: dict[str, Any]) -> str:
    return f"""너는 HS-CAD main merge operator다.

목표:
PR #56을 검토하고 main 병합 가능 여부를 판단한다.

PR #56:
{package['pr56_context']['pr_url']}

절대 금지:
- main에 직접 push하지 말 것
- final live runner 구현하지 말 것
- ZWCAD COM SendCommand 실행하지 말 것
- XiCAD alias 실행하지 말 것
- Domain Rule Command Plan 실행하지 말 것
- 원본 DWG 수정하지 말 것
- outputs/**, scratch/**, *.dwg, *.dxf, *.zip, cache 파일 커밋하지 말 것

최종 검증 명령:
{chr(10).join(f'- {cmd}' for cmd in package['final_pre_merge_validation_commands'])}

선택 ruff:
- {package['optional_ruff_command']}

허용 범위:
{chr(10).join(f'- {item}' for item in package['main_merge_allowed_scope'])}

금지 범위:
{chr(10).join(f'- {item}' for item in package['main_merge_disallowed_scope'])}

검증이 모두 통과하면:
- PR #56을 인간 검토 후 main 병합 후보로 승인한다.
- main 병합 후 로컬 Windows/ZWCAD 검증은 별도 수동 단계로 진행한다.
"""


def build_post_merge_local_validation_prompt(package: dict[str, Any]) -> str:
    lines = [
        "너는 HS-CAD post-merge local-only validation agent다.",
        "",
        "이 작업은 main 병합 후 Windows/ZWCAD/XiCAD 로컬 환경에서만 진행한다.",
        "원본 DWG를 절대 수정하지 말고 copied DWG만 사용한다.",
        "final live runner는 구현하지 않는다.",
        "",
        "금지:",
        "- original DWG 수정",
        "- unknown alias 실행",
        "- destructive alias 실행",
        "- 자동 operator approval",
        "- batch SendCommand",
        "- final live runner 구현",
        "",
        "실행 순서:",
        "",
    ]
    for index, step in enumerate(package["post_merge_local_validation_commands"], start=1):
        lines.append(f"{index}. {step['title']}")
        lines.append(f"   환경: {step['environment']}")
        lines.append(f"   명령:")
        lines.append(f"   {step['command']}")
        lines.append("   확인:")
        for item in step["confirm"]:
            lines.append(f"   - {item}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def write_main_merge_operator_review_outputs(
    repo_root: str | Path = ".",
    *,
    pr56_workspace: str | Path = "outputs/pr55_main_ready_review_only_validation",
    out_dir: str | Path = "outputs/main_merge_operator_review",
) -> dict[str, Any]:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    package = build_main_merge_operator_review(repo_root=repo_root, pr56_workspace=pr56_workspace)

    package_json = out / "MAIN_MERGE_OPERATOR_REVIEW_PACKAGE.json"
    package_md = out / "MAIN_MERGE_OPERATOR_REVIEW_PACKAGE.md"
    merge_prompt = out / "MAIN_MERGE_OPERATOR_PROMPT.md"
    local_prompt = out / "POST_MERGE_LOCAL_VALIDATION_PROMPT.md"

    package_json.write_text(json.dumps(package, ensure_ascii=False, indent=2), encoding="utf-8")
    package_md.write_text(render_operator_review_markdown(package), encoding="utf-8")
    merge_prompt.write_text(build_main_merge_operator_prompt(package), encoding="utf-8")
    local_prompt.write_text(build_post_merge_local_validation_prompt(package), encoding="utf-8")

    return {
        "status": package["status"],
        "out_dir": str(out),
        "package_json": str(package_json),
        "package_md": str(package_md),
        "main_merge_operator_prompt": str(merge_prompt),
        "post_merge_local_validation_prompt": str(local_prompt),
        "safety": package["safety"],
    }
