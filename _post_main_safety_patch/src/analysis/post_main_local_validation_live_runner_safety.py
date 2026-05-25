from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PR56_CONTEXT = {
    "branch": "integration/main-ready-review-only-pipeline",
    "pr_url": "https://github.com/khs0927/HS-CAD/pull/56",
    "main_ready_judgment": "yes",
    "reported_validation": {
        "targeted": "3 passed",
        "full_pytest": "206 passed, 16 skipped",
        "compileall": "passed",
        "cli_smoke": "passed",
    },
}

OPERATOR_REVIEW_EXPECTED = {
    "branch": "integration/main-merge-operator-review",
    "artifact": "MAIN_MERGE_OPERATOR_REVIEW_PACKAGE.json",
    "expected_statuses": ["ready_for_operator_main_merge_review", "review_required"],
}


LOCAL_VALIDATION_COMMANDS = [
    {
        "id": "local-01-copied-dwg-scan",
        "title": "Copied DWG scan validation",
        "phase": "post-main-local-validation",
        "environment": "Windows + ZWCAD installed",
        "command": 'python -X utf8 -m src.main zwcad-copy-scan-validate --original-dwg "C:/cad/test/original.dwg" --working-copy-dwg "C:/cad/test_work/copy.dwg" --out-dir outputs/zwcad_copy_validation_live',
        "required_inputs": [
            "original_dwg",
            "working_copy_dwg",
        ],
        "required_confirmations": [
            "original_dwg_hash_before_recorded",
            "original_dwg_hash_after_unchanged",
            "working_copy_path_differs_from_original",
            "audit_log_written",
            "no_sendcommand_for_scan",
        ],
        "status": "manual_only_pending",
    },
    {
        "id": "local-02-copied-dwg-saveas",
        "title": "Copied DWG SaveAs validation",
        "phase": "post-main-local-validation",
        "environment": "Windows + ZWCAD installed",
        "command": 'python -X utf8 -m src.main zwcad-copy-saveas-validate --original-dwg "C:/cad/test/original.dwg" --working-copy-dwg "C:/cad/test_work/copy.dwg" --save-as-target "C:/cad/test_work/result.dwg" --out-dir outputs/zwcad_copy_saveas_validation_live --overwrite-copy',
        "required_inputs": [
            "original_dwg",
            "working_copy_dwg",
            "save_as_target",
        ],
        "required_confirmations": [
            "save_as_target_differs_from_original",
            "original_dwg_hash_after_unchanged",
            "before_scan_written",
            "after_scan_written",
            "delta_report_written",
            "audit_log_written",
        ],
        "status": "manual_only_pending",
    },
    {
        "id": "local-03-xicad-policy-candidates",
        "title": "XiCAD policy candidate validation from C:/xicad",
        "phase": "post-main-local-validation",
        "environment": "Windows + C:/xicad",
        "command": 'python -X utf8 -m src.main xicad-policy-candidates --xicad-root C:/xicad --out-dir outputs/xicad_policy_candidates_verify',
        "required_inputs": [
            "xicad_root",
        ],
        "required_confirmations": [
            "allowed_for_execution_false",
            "execution_allowed_aliases_empty",
            "unknown_aliases_blocked",
            "destructive_aliases_blocked",
            "policy_artifacts_written",
        ],
        "status": "manual_only_pending",
    },
    {
        "id": "local-04-phase12-manual-candidate-guard",
        "title": "Phase 12 manual candidate guard only",
        "phase": "post-main-local-validation",
        "environment": "Windows + copied DWG + allowlist artifacts",
        "command": "python -X utf8 -m src.main hscad-analysis-phase12-manual-live-candidate --workspace outputs/phase10_11_domain_copy_verify --alias WAL --manual-live-flag --operator-approved --out-dir outputs/phase12_manual_live_candidate_verify",
        "required_inputs": [
            "phase11_copy_validation_cli_plan",
            "xicad_alias_allowlist_plan",
            "manual_live_flag",
            "operator_approved",
        ],
        "required_confirmations": [
            "candidate_created_or_blocked_with_reason",
            "execution_allowed_false",
            "sendcommand_allowed_false",
            "final_runner_guard_not_implemented",
            "original_dwg_not_mutated",
        ],
        "status": "manual_only_pending",
    },
]


FINAL_LIVE_RUNNER_SAFETY_REQUIREMENTS = [
    {
        "id": "flr-req-01",
        "title": "Copied DWG only",
        "requirement": "Final live runner must refuse original DWG path and require a distinct working copy.",
        "enforcement": "path inequality + hash audit",
    },
    {
        "id": "flr-req-02",
        "title": "Distinct SaveAs target",
        "requirement": "save_as_target must differ from original_dwg and working_copy_dwg.",
        "enforcement": "path inequality",
    },
    {
        "id": "flr-req-03",
        "title": "Allowlist alias only",
        "requirement": "Alias must be present in verified allowlist and absent from blocked list.",
        "enforcement": "allowlist policy check",
    },
    {
        "id": "flr-req-04",
        "title": "Unknown/destructive aliases blocked",
        "requirement": "Unknown and destructive aliases must fail closed.",
        "enforcement": "deny-by-default policy",
    },
    {
        "id": "flr-req-05",
        "title": "Manual approval required",
        "requirement": "operator_approved and manual_live_flag must both be explicit true.",
        "enforcement": "two explicit flags, no env default",
    },
    {
        "id": "flr-req-06",
        "title": "One command only for first live runner",
        "requirement": "Initial live runner can execute at most one harmless command.",
        "enforcement": "single-command policy",
    },
    {
        "id": "flr-req-07",
        "title": "Before/after scan required",
        "requirement": "Runner must scan working copy before and after execution.",
        "enforcement": "mandatory artifacts",
    },
    {
        "id": "flr-req-08",
        "title": "Delta report required",
        "requirement": "Runner must produce a delta report comparing before/after scan.",
        "enforcement": "mandatory artifact",
    },
    {
        "id": "flr-req-09",
        "title": "Audit log required",
        "requirement": "Runner must log every safety decision, command candidate, and result.",
        "enforcement": "append-only audit artifact",
    },
    {
        "id": "flr-req-10",
        "title": "Original hash unchanged",
        "requirement": "Original DWG hash before/after must match.",
        "enforcement": "sha256 before/after verification",
    },
    {
        "id": "flr-req-11",
        "title": "Default disabled",
        "requirement": "Final live runner must refuse execution unless all explicit flags and policy checks pass.",
        "enforcement": "fail-closed default",
    },
]


RISK_REGISTER = [
    {
        "risk_id": "risk-001-original-mutation",
        "title": "Original DWG mutation",
        "severity": "critical",
        "mitigation": "Refuse original path, copied-DWG only, before/after hash check.",
    },
    {
        "risk_id": "risk-002-destructive-command",
        "title": "Destructive CAD/XiCAD command execution",
        "severity": "critical",
        "mitigation": "Deny-by-default alias policy, allowlist-only, single harmless command first.",
    },
    {
        "risk_id": "risk-003-operator-approval-bypass",
        "title": "Automatic or implied approval",
        "severity": "high",
        "mitigation": "Require explicit operator_approved and manual_live_flag from CLI.",
    },
    {
        "risk_id": "risk-004-batch-execution",
        "title": "Unreviewed batch execution",
        "severity": "high",
        "mitigation": "First implementation allows only one command.",
    },
    {
        "risk_id": "risk-005-delta-blindness",
        "title": "No before/after comparison",
        "severity": "high",
        "mitigation": "Mandatory before/after scan and delta artifact.",
    },
    {
        "risk_id": "risk-006-audit-gap",
        "title": "No audit trail",
        "severity": "medium",
        "mitigation": "Append-only audit log required.",
    },
]


@dataclass(frozen=True)
class BundleGate:
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


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _safety() -> dict[str, Any]:
    return {
        "main_merge_performed_by_this_bundle": False,
        "local_validation_executed_by_this_bundle": False,
        "final_live_runner_implemented": False,
        "cad_execution_allowed_by_default": False,
        "zwcad_com_sendcommand_allowed": False,
        "xicad_alias_execution_allowed": False,
        "domain_rule_command_execution_allowed": False,
        "original_dwg_mutation_allowed": False,
        "post_main_local_validation_manual_only": True,
        "final_live_runner_requires_separate_safety_spec_pr": True,
    }


def build_post_main_local_validation_live_runner_safety_bundle(
    repo_root: str | Path = ".",
    operator_review_workspace: str | Path = "outputs/main_merge_operator_review",
) -> dict[str, Any]:
    repo = Path(repo_root)
    workspace = Path(operator_review_workspace)
    gates: list[BundleGate] = []

    operator_package_path = workspace / "MAIN_MERGE_OPERATOR_REVIEW_PACKAGE.json"
    operator_package = _load_json(operator_package_path)

    if operator_package:
        gates.append(
            BundleGate(
                id="gate:operator-review-package",
                title="Main merge operator review package exists",
                status="ok",
                evidence=[str(operator_package_path), str(operator_package.get("status", ""))],
                next_action="Human operator may use the package for main merge decision.",
            )
        )
    else:
        gates.append(
            BundleGate(
                id="gate:operator-review-package",
                title="Main merge operator review package exists",
                status="review_required",
                blocked_reasons=[f"missing:{operator_package_path}"],
                next_action="Run hscad-main-merge-operator-review or use PR #56 validation report manually.",
            )
        )

    gates.append(
        BundleGate(
            id="gate:post-main-local-validation-manual-only",
            title="Post-main local validation remains manual-only",
            status="ok",
            evidence=[step["id"] for step in LOCAL_VALIDATION_COMMANDS],
            next_action="Do not run Windows/ZWCAD validation in CI or this bundle.",
        )
    )

    gates.append(
        BundleGate(
            id="gate:final-live-runner-deferred",
            title="Final live runner remains deferred",
            status="ok",
            evidence=[req["id"] for req in FINAL_LIVE_RUNNER_SAFETY_REQUIREMENTS],
            next_action="Create a separate safety-spec PR before any live runner implementation.",
        )
    )

    return {
        "task": "post_main_local_validation_live_runner_safety_bundle",
        "generated_at": _now(),
        "repo_root": str(repo),
        "operator_review_workspace": str(workspace),
        "status": "ready_for_operator_review_and_post_main_planning",
        "pr56_context": PR56_CONTEXT,
        "operator_review_expected": OPERATOR_REVIEW_EXPECTED,
        "gates": [gate.to_dict() for gate in gates],
        "post_main_local_validation_commands": LOCAL_VALIDATION_COMMANDS,
        "final_live_runner_safety_requirements": FINAL_LIVE_RUNNER_SAFETY_REQUIREMENTS,
        "risk_register": RISK_REGISTER,
        "next_pr_sequence": [
            "human/main-merge-review",
            "local/post-main-zwcad-xicad-validation",
            "design/final-live-runner-safety-spec",
            "feat/final-live-runner-manual-copy-only",
        ],
        "safety": _safety(),
    }


def render_bundle_markdown(package: dict[str, Any]) -> str:
    lines = [
        "# HS-CAD Post-main Local Validation & Final Live Runner Safety Bundle",
        "",
        "## Summary",
        "",
        f"- Status: `{package['status']}`",
        f"- PR #56: {package['pr56_context']['pr_url']}",
        "",
        "## Gates",
        "",
    ]

    for gate in package["gates"]:
        lines.append(f"### {gate['id']}")
        lines.append("")
        lines.append(f"- Title: {gate['title']}")
        lines.append(f"- Status: `{gate['status']}`")
        if gate["blocked_reasons"]:
            lines.append(f"- Blocked reasons: {', '.join(gate['blocked_reasons'])}")
        lines.append(f"- Next action: {gate['next_action']}")
        lines.append("")

    lines += ["## Post-main Local Validation Commands", ""]
    for step in package["post_main_local_validation_commands"]:
        lines.append(f"### {step['id']}")
        lines.append("")
        lines.append(f"- Title: {step['title']}")
        lines.append(f"- Environment: {step['environment']}")
        lines.append(f"- Status: `{step['status']}`")
        lines.append("```powershell")
        lines.append(step["command"])
        lines.append("```")
        lines.append("Confirm:")
        for item in step["required_confirmations"]:
            lines.append(f"- {item}")
        lines.append("")

    lines += ["## Final Live Runner Safety Requirements", ""]
    for req in package["final_live_runner_safety_requirements"]:
        lines.append(f"- `{req['id']}`: {req['title']} — {req['requirement']}")

    lines += ["", "## Risk Register", ""]
    for risk in package["risk_register"]:
        lines.append(f"- `{risk['risk_id']}` / `{risk['severity']}`: {risk['title']} — {risk['mitigation']}")

    lines += ["", "## Safety", ""]
    for key, value in package["safety"].items():
        lines.append(f"- `{key}`: `{value}`")

    return "\n".join(lines).rstrip() + "\n"


def build_main_merge_operator_prompt(package: dict[str, Any]) -> str:
    return f"""너는 HS-CAD main merge operator다.

목표:
PR #56과 operator review package를 검토하고 main 병합 여부를 인간 판단으로 결정한다.

PR #56:
{package['pr56_context']['pr_url']}

병합 허용 범위:
- review-only analysis pipeline
- plan-only Domain Rule bridge
- copied-DWG validation planning
- manual live candidate guard
- safety policy docs

병합 금지 범위:
- final live runner
- ZWCAD COM SendCommand execution
- XiCAD alias execution
- Domain Rule Command Plan execution
- original DWG mutation
- automatic operator approval

최종 확인:
- full pytest 통과
- src.main --help 통과
- outputs/DWG/DXF/cache 미커밋
- final live runner 미구현
- SendCommand 실행 미활성
- main 병합은 인간 검토 후 수동으로만 진행
"""


def build_post_main_local_validation_prompt(package: dict[str, Any]) -> str:
    lines = [
        "너는 HS-CAD post-main local validation agent다.",
        "",
        "이 작업은 main 병합 후 Windows/ZWCAD/XiCAD 환경에서만 수동 실행한다.",
        "원본 DWG를 절대 수정하지 말고 copied DWG만 사용한다.",
        "final live runner는 구현하지 않는다.",
        "",
        "검증 순서:",
        "",
    ]
    for index, step in enumerate(package["post_main_local_validation_commands"], start=1):
        lines.append(f"{index}. {step['title']}")
        lines.append(f"   환경: {step['environment']}")
        lines.append(f"   명령: {step['command']}")
        lines.append("   확인:")
        for item in step["required_confirmations"]:
            lines.append(f"   - {item}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def build_final_live_runner_safety_spec_prompt(package: dict[str, Any]) -> str:
    lines = [
        "너는 HS-CAD final live runner safety spec 작성 에이전트다.",
        "",
        "이 작업은 실행기 구현이 아니라 안전 설계 PR 작성이다.",
        "final live runner 코드를 구현하지 말고, safety spec / policy / tests plan / risk register만 작성한다.",
        "",
        "필수 안전 요구사항:",
        "",
    ]
    for req in package["final_live_runner_safety_requirements"]:
        lines.append(f"- {req['id']} {req['title']}: {req['requirement']} / enforcement={req['enforcement']}")

    lines += [
        "",
        "작성 대상 문서:",
        "- docs/107_final_live_runner_safety_spec.md",
        "- docs/108_final_live_runner_execution_policy.md",
        "- docs/109_final_live_runner_test_plan.md",
        "- docs/110_final_live_runner_risk_register.md",
        "",
        "금지:",
        "- SendCommand 실행 코드 작성",
        "- XiCAD alias 실행 코드 작성",
        "- final live runner CLI 구현",
        "- original DWG 수정 허용",
    ]
    return "\n".join(lines).rstrip() + "\n"


def write_post_main_bundle_outputs(
    repo_root: str | Path = ".",
    *,
    operator_review_workspace: str | Path = "outputs/main_merge_operator_review",
    out_dir: str | Path = "outputs/post_main_local_validation_live_runner_safety",
) -> dict[str, Any]:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    package = build_post_main_local_validation_live_runner_safety_bundle(
        repo_root=repo_root,
        operator_review_workspace=operator_review_workspace,
    )

    paths = {
        "package_json": out / "POST_MAIN_LOCAL_VALIDATION_LIVE_RUNNER_SAFETY_BUNDLE.json",
        "package_md": out / "POST_MAIN_LOCAL_VALIDATION_LIVE_RUNNER_SAFETY_BUNDLE.md",
        "local_validation_json": out / "POST_MAIN_LOCAL_VALIDATION_COMMANDS.json",
        "final_live_runner_spec_json": out / "FINAL_LIVE_RUNNER_SAFETY_REQUIREMENTS.json",
        "risk_register_json": out / "FINAL_LIVE_RUNNER_RISK_REGISTER.json",
        "operator_prompt": out / "MAIN_MERGE_OPERATOR_PROMPT.md",
        "local_validation_prompt": out / "POST_MAIN_LOCAL_VALIDATION_PROMPT.md",
        "safety_spec_prompt": out / "FINAL_LIVE_RUNNER_SAFETY_SPEC_PROMPT.md",
    }

    paths["package_json"].write_text(json.dumps(package, ensure_ascii=False, indent=2), encoding="utf-8")
    paths["package_md"].write_text(render_bundle_markdown(package), encoding="utf-8")
    paths["local_validation_json"].write_text(
        json.dumps(package["post_main_local_validation_commands"], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    paths["final_live_runner_spec_json"].write_text(
        json.dumps(package["final_live_runner_safety_requirements"], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    paths["risk_register_json"].write_text(
        json.dumps(package["risk_register"], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    paths["operator_prompt"].write_text(build_main_merge_operator_prompt(package), encoding="utf-8")
    paths["local_validation_prompt"].write_text(build_post_main_local_validation_prompt(package), encoding="utf-8")
    paths["safety_spec_prompt"].write_text(build_final_live_runner_safety_spec_prompt(package), encoding="utf-8")

    return {
        "status": package["status"],
        "out_dir": str(out),
        **{key: str(value) for key, value in paths.items()},
        "safety": package["safety"],
    }
