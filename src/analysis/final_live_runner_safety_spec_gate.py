from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PR59_CONTEXT = {
    "branch": "human/main-merge-review-gate",
    "pr_url": "https://github.com/khs0927/HS-CAD/pull/59",
    "reported_validation": "227 passed, 16 skipped",
    "human_review_status": "ready",
}


LOCAL_RECORDER_CONTEXT = {
    "branch": "local/post-main-validation-recorder-final-runner-spec",
    "purpose": "Records local validation results and blocks live runner implementation until gates are satisfied.",
    "expected_summary": "outputs/local_validation_recorder/LOCAL_VALIDATION_RESULT_SUMMARY.json",
}


REQUIRED_LOCAL_VALIDATION_IDS = [
    "local-01-copied-dwg-scan",
    "local-02-copied-dwg-saveas",
    "local-03-xicad-policy-candidates",
    "local-04-phase12-candidate-guard",
]


REQUIRED_SAFETY_DOCS = [
    "docs/118_final_live_runner_safety_spec.md",
    "docs/119_final_live_runner_execution_policy.md",
    "docs/120_final_live_runner_test_plan.md",
    "docs/121_final_live_runner_risk_register.md",
    "docs/122_final_live_runner_manual_copy_only_interface.md",
]


MINIMUM_IMPLEMENTATION_CONSTRAINTS = [
    {
        "id": "constraint-001-copied-dwg-only",
        "title": "Copied DWG only",
        "rule": "Runner must refuse original_dwg as a target and require a distinct working_copy_dwg.",
        "enforcement": "Path inequality and original SHA256 before/after verification.",
        "blocking": True,
    },
    {
        "id": "constraint-002-distinct-saveas",
        "title": "Distinct SaveAs target",
        "rule": "save_as_target must differ from original_dwg and working_copy_dwg.",
        "enforcement": "Path inequality check before any COM call.",
        "blocking": True,
    },
    {
        "id": "constraint-003-allowlist-only",
        "title": "Allowlist alias only",
        "rule": "Alias must exist in a verified allowlist and must not appear in blocked/destructive sets.",
        "enforcement": "Deny-by-default alias policy.",
        "blocking": True,
    },
    {
        "id": "constraint-004-explicit-human-approval",
        "title": "Explicit human approval",
        "rule": "manual_live_flag and operator_approved must both be explicit true.",
        "enforcement": "CLI flags only; no environment default and no config override.",
        "blocking": True,
    },
    {
        "id": "constraint-005-single-command-first",
        "title": "Single harmless command for first runner",
        "rule": "Initial live runner may execute at most one harmless allowlisted command.",
        "enforcement": "Reject command arrays with length other than 1.",
        "blocking": True,
    },
    {
        "id": "constraint-006-before-after-scan",
        "title": "Before/after scan required",
        "rule": "Runner must generate before and after scan artifacts.",
        "enforcement": "Execution result is invalid without both artifacts.",
        "blocking": True,
    },
    {
        "id": "constraint-007-delta-report",
        "title": "Delta report required",
        "rule": "Runner must generate a delta report comparing before and after scans.",
        "enforcement": "Execution result is invalid without delta artifact.",
        "blocking": True,
    },
    {
        "id": "constraint-008-audit-log",
        "title": "Audit log required",
        "rule": "Every decision, rejected condition, and command candidate must be logged.",
        "enforcement": "Append-only audit artifact.",
        "blocking": True,
    },
    {
        "id": "constraint-009-original-hash-unchanged",
        "title": "Original DWG hash unchanged",
        "rule": "Original DWG SHA256 before and after must match.",
        "enforcement": "Hash verification after runner completes or fails.",
        "blocking": True,
    },
    {
        "id": "constraint-010-default-disabled",
        "title": "Default disabled and fail-closed",
        "rule": "Runner must not execute unless every gate passes.",
        "enforcement": "No permissive fallback.",
        "blocking": True,
    },
]


TEST_MATRIX = [
    {"id": "test-policy-001", "case": "reject original DWG target", "expected": "blocked"},
    {"id": "test-policy-002", "case": "reject same save_as_target", "expected": "blocked"},
    {"id": "test-policy-003", "case": "reject missing operator_approved", "expected": "blocked"},
    {"id": "test-policy-004", "case": "reject missing manual_live_flag", "expected": "blocked"},
    {"id": "test-policy-005", "case": "reject unknown alias", "expected": "blocked"},
    {"id": "test-policy-006", "case": "reject destructive alias", "expected": "blocked"},
    {"id": "test-policy-007", "case": "reject batch commands", "expected": "blocked"},
    {"id": "test-policy-008", "case": "require before scan", "expected": "blocked if missing"},
    {"id": "test-policy-009", "case": "require after scan", "expected": "blocked if missing"},
    {"id": "test-policy-010", "case": "require delta report", "expected": "blocked if missing"},
    {"id": "test-policy-011", "case": "require audit log", "expected": "blocked if missing"},
    {"id": "test-policy-012", "case": "original hash changed", "expected": "critical failure"},
    {"id": "test-policy-013", "case": "single harmless allowlisted copied-DWG candidate", "expected": "candidate only, implementation separate"},
]


@dataclass(frozen=True)
class SafetySpecGate:
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
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        return {"__json_error__": str(exc)}


def _safety() -> dict[str, Any]:
    return {
        "this_package_implements_runner": False,
        "cad_execution_allowed": False,
        "zwcad_com_sendcommand_allowed": False,
        "xicad_alias_execution_allowed": False,
        "domain_rule_command_execution_allowed": False,
        "original_dwg_mutation_allowed": False,
        "final_live_runner_implementation_allowed": False,
        "safety_spec_review_only": True,
        "implementation_requires_separate_pr": True,
    }


def build_final_live_runner_safety_spec_gate(
    repo_root: str | Path = ".",
    local_validation_summary_json: str | Path = "outputs/local_validation_recorder/LOCAL_VALIDATION_RESULT_SUMMARY.json",
) -> dict[str, Any]:
    repo = Path(repo_root)
    summary_path = Path(local_validation_summary_json)
    summary = _load_json(summary_path)

    gates: list[SafetySpecGate] = []

    if not summary:
        gates.append(
            SafetySpecGate(
                id="gate:local-validation-summary",
                title="Local validation summary exists",
                status="blocked",
                blocked_reasons=[f"missing:{summary_path}"],
                next_action="Run hscad-local-validation-recorder after local validation result files are filled.",
            )
        )
    elif "__json_error__" in summary:
        gates.append(
            SafetySpecGate(
                id="gate:local-validation-summary",
                title="Local validation summary is valid JSON",
                status="blocked",
                blocked_reasons=[summary["__json_error__"]],
                next_action="Fix malformed LOCAL_VALIDATION_RESULT_SUMMARY.json.",
            )
        )
    else:
        all_passed = summary.get("all_local_validations_passed") is True
        gates.append(
            SafetySpecGate(
                id="gate:local-validation-summary",
                title="All manual local validations passed",
                status="ok" if all_passed else "blocked",
                evidence=[f"status={summary.get('status')}", f"all_local_validations_passed={summary.get('all_local_validations_passed')}"],
                blocked_reasons=[] if all_passed else ["local_validations_not_all_passed"],
                next_action="Complete manual Windows/ZWCAD/C:/xicad validations before implementation PR.",
            )
        )

    present_docs = [doc for doc in REQUIRED_SAFETY_DOCS if (repo / doc).exists()]
    missing_docs = [doc for doc in REQUIRED_SAFETY_DOCS if not (repo / doc).exists()]
    gates.append(
        SafetySpecGate(
            id="gate:safety-spec-docs",
            title="Final live runner safety spec docs exist",
            status="ok" if not missing_docs else "blocked",
            evidence=present_docs,
            blocked_reasons=[f"missing:{doc}" for doc in missing_docs],
            next_action="Add missing docs/118~122 safety spec documents.",
        )
    )

    gates.append(
        SafetySpecGate(
            id="gate:implementation-deferred",
            title="Runner implementation remains deferred",
            status="ok",
            evidence=["final_live_runner_implementation_allowed=false", "implementation_requires_separate_pr=true"],
            next_action="Only create safety spec approval package in this PR.",
        )
    )

    blocked = [gate for gate in gates if gate.status == "blocked"]
    status = "blocked" if blocked else "ready_for_safety_spec_review"

    return {
        "task": "final_live_runner_safety_spec_gate",
        "generated_at": _now(),
        "repo_root": str(repo),
        "local_validation_summary_json": str(summary_path),
        "status": status,
        "pr59_context": PR59_CONTEXT,
        "local_recorder_context": LOCAL_RECORDER_CONTEXT,
        "gates": [gate.to_dict() for gate in gates],
        "minimum_implementation_constraints": MINIMUM_IMPLEMENTATION_CONSTRAINTS,
        "test_matrix": TEST_MATRIX,
        "required_local_validation_ids": REQUIRED_LOCAL_VALIDATION_IDS,
        "required_safety_docs": REQUIRED_SAFETY_DOCS,
        "approval_decision": {
            "safety_spec_pr_can_be_reviewed": status == "ready_for_safety_spec_review",
            "implementation_pr_can_start": False,
            "reason": "Implementation requires a separate PR even after this safety spec gate passes.",
        },
        "safety": _safety(),
    }


def render_safety_spec_gate_markdown(package: dict[str, Any]) -> str:
    lines = [
        "# HS-CAD Final Live Runner Safety Spec Gate",
        "",
        f"- Status: `{package['status']}`",
        f"- PR #59: {package['pr59_context']['pr_url']}",
        f"- Implementation PR can start: `{package['approval_decision']['implementation_pr_can_start']}`",
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

    lines += ["## Minimum Implementation Constraints", ""]
    for item in package["minimum_implementation_constraints"]:
        lines.append(f"- `{item['id']}`: {item['title']} — {item['rule']}")

    lines += ["", "## Test Matrix", ""]
    for test in package["test_matrix"]:
        lines.append(f"- `{test['id']}`: {test['case']} -> {test['expected']}")

    lines += ["", "## Safety", ""]
    for key, value in package["safety"].items():
        lines.append(f"- `{key}`: `{value}`")

    return "\n".join(lines).rstrip() + "\n"


def build_safety_spec_review_prompt(package: dict[str, Any]) -> str:
    return f"""너는 HS-CAD final live runner safety spec reviewer다.

목표:
final live runner 구현 전 safety spec PR을 검토한다.

중요:
이 작업은 runner 구현이 아니다.
SendCommand 코드를 작성하지 않는다.
XiCAD alias 실행 코드를 작성하지 않는다.
원본 DWG mutation을 허용하지 않는다.

현재 상태:
- PR #59: {package['pr59_context']['pr_url']}
- Safety spec gate status: {package['status']}
- Implementation PR can start: {package['approval_decision']['implementation_pr_can_start']}

검토해야 할 최소 구현 제약조건:
{chr(10).join(f"- {item['id']}: {item['title']}" for item in package['minimum_implementation_constraints'])}

테스트 매트릭스:
{chr(10).join(f"- {item['id']}: {item['case']} -> {item['expected']}" for item in package['test_matrix'])}

결론:
이 PR에서는 safety spec만 승인 여부를 검토한다.
실제 final live runner 구현은 별도 PR에서만 진행한다.
"""


def write_final_live_runner_safety_spec_gate_outputs(
    repo_root: str | Path = ".",
    *,
    local_validation_summary_json: str | Path = "outputs/local_validation_recorder/LOCAL_VALIDATION_RESULT_SUMMARY.json",
    out_dir: str | Path = "outputs/final_live_runner_safety_spec_gate",
) -> dict[str, Any]:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    package = build_final_live_runner_safety_spec_gate(
        repo_root=repo_root,
        local_validation_summary_json=local_validation_summary_json,
    )

    package_json = out / "FINAL_LIVE_RUNNER_SAFETY_SPEC_GATE.json"
    package_md = out / "FINAL_LIVE_RUNNER_SAFETY_SPEC_GATE.md"
    constraints_json = out / "MINIMUM_IMPLEMENTATION_CONSTRAINTS.json"
    test_matrix_json = out / "FINAL_LIVE_RUNNER_TEST_MATRIX.json"
    review_prompt = out / "FINAL_LIVE_RUNNER_SAFETY_SPEC_REVIEW_PROMPT.md"

    package_json.write_text(json.dumps(package, ensure_ascii=False, indent=2), encoding="utf-8")
    package_md.write_text(render_safety_spec_gate_markdown(package), encoding="utf-8")
    constraints_json.write_text(json.dumps(MINIMUM_IMPLEMENTATION_CONSTRAINTS, ensure_ascii=False, indent=2), encoding="utf-8")
    test_matrix_json.write_text(json.dumps(TEST_MATRIX, ensure_ascii=False, indent=2), encoding="utf-8")
    review_prompt.write_text(build_safety_spec_review_prompt(package), encoding="utf-8")

    return {
        "status": package["status"],
        "out_dir": str(out),
        "package_json": str(package_json),
        "package_md": str(package_md),
        "constraints_json": str(constraints_json),
        "test_matrix_json": str(test_matrix_json),
        "review_prompt": str(review_prompt),
        "safety": package["safety"],
    }
