from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PR64_CONTEXT = {
    "assumed_base_branch": "local/local-validation-evidence-review",
    "previous_pr": "https://github.com/khs0927/HS-CAD/pull/63",
    "previous_stage": "Local Validation Evidence Review Gate",
    "purpose": "Finalize local evidence and decide whether final live runner safety spec approval can proceed.",
    "important_note": "If PR #64 already exists for evidence review, replace this context with the actual PR URL in docs/140.",
}


REQUIRED_EVIDENCE_REVIEW_STATUSES = [
    "ready_for_safety_spec_review",
]


REQUIRED_REVIEW_FILES = [
    "outputs/local_validation_evidence_review/LOCAL_VALIDATION_EVIDENCE_REVIEW.json",
    "outputs/local_validation_recorder/LOCAL_VALIDATION_RESULT_SUMMARY.json",
    "outputs/final_live_runner_safety_spec_gate/FINAL_LIVE_RUNNER_SAFETY_SPEC_GATE.json",
]


SAFETY_SPEC_APPROVAL_CRITERIA = [
    {
        "id": "approval-001-local-evidence-ready",
        "title": "Local evidence review ready",
        "source": "LOCAL_VALIDATION_EVIDENCE_REVIEW.json",
        "required": {"status": "ready_for_safety_spec_review"},
    },
    {
        "id": "approval-002-recorder-all-passed",
        "title": "Recorder summary all passed",
        "source": "LOCAL_VALIDATION_RESULT_SUMMARY.json",
        "required": {"all_local_validations_passed": True, "status": "passed"},
    },
    {
        "id": "approval-003-safety-gate-ready-or-blocked-expected",
        "title": "Final safety gate checked",
        "source": "FINAL_LIVE_RUNNER_SAFETY_SPEC_GATE.json",
        "required_any": [
            {"status": "ready_for_safety_spec_review"},
            {"status": "blocked", "approval_decision.safety_spec_pr_can_be_reviewed": False},
        ],
        "note": "If blocked, implementation must remain impossible; only evidence gaps may be fixed.",
    },
]


IMPLEMENTATION_PR_HARD_GATES = [
    "human_main_merge_review_completed",
    "review_only_main_scope_confirmed",
    "local_validation_evidence_review_ready",
    "local_validation_recorder_all_passed",
    "final_live_runner_safety_spec_gate_reviewed",
    "safety_spec_approved_by_human",
    "one_command_copy_only_scope_confirmed",
    "rollback_manual_procedure_documented",
    "audit_artifact_schema_reviewed",
]


@dataclass(frozen=True)
class ApprovalGate:
    id: str
    title: str
    status: str
    source: str
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


def _get_nested(payload: dict[str, Any], dotted: str) -> Any:
    current: Any = payload
    for part in dotted.split("."):
        if not isinstance(current, dict) or part not in current:
            return None
        current = current[part]
    return current


def _matches(payload: dict[str, Any], required: dict[str, Any]) -> tuple[bool, list[str]]:
    failures: list[str] = []
    for key, expected in required.items():
        actual = _get_nested(payload, key)
        if actual != expected:
            failures.append(f"{key}: expected {expected!r}, got {actual!r}")
    return not failures, failures


def _safety() -> dict[str, Any]:
    return {
        "this_package_runs_cad": False,
        "this_package_runs_powershell": False,
        "this_package_calls_zwcad_com": False,
        "this_package_calls_sendcommand": False,
        "this_package_executes_xicad_alias": False,
        "this_package_mutates_original_dwg": False,
        "this_package_implements_final_live_runner": False,
        "safety_spec_approval_only": True,
        "implementation_pr_allowed_by_this_package": False,
        "implementation_requires_separate_pr": True,
    }


def evaluate_approval_gate(repo_root: Path, criterion: dict[str, Any]) -> ApprovalGate:
    source_path = repo_root / "outputs"
    source_name = criterion["source"]

    if source_name == "LOCAL_VALIDATION_EVIDENCE_REVIEW.json":
        path = repo_root / "outputs/local_validation_evidence_review/LOCAL_VALIDATION_EVIDENCE_REVIEW.json"
    elif source_name == "LOCAL_VALIDATION_RESULT_SUMMARY.json":
        path = repo_root / "outputs/local_validation_recorder/LOCAL_VALIDATION_RESULT_SUMMARY.json"
    elif source_name == "FINAL_LIVE_RUNNER_SAFETY_SPEC_GATE.json":
        path = repo_root / "outputs/final_live_runner_safety_spec_gate/FINAL_LIVE_RUNNER_SAFETY_SPEC_GATE.json"
    else:
        path = source_path / source_name

    payload = _load_json(path)
    if not payload:
        return ApprovalGate(
            id=criterion["id"],
            title=criterion["title"],
            status="missing",
            source=str(path),
            blocked_reasons=[f"missing:{path}"],
            next_action="Generate or copy the required evidence artifact.",
        )

    if "__json_error__" in payload:
        return ApprovalGate(
            id=criterion["id"],
            title=criterion["title"],
            status="invalid_json",
            source=str(path),
            blocked_reasons=[payload["__json_error__"]],
            next_action="Fix JSON syntax.",
        )

    if "required" in criterion:
        ok, failures = _matches(payload, criterion["required"])
        return ApprovalGate(
            id=criterion["id"],
            title=criterion["title"],
            status="passed" if ok else "blocked",
            source=str(path),
            evidence=[f"{key}={_get_nested(payload, key)!r}" for key in criterion["required"]],
            blocked_reasons=failures,
            next_action="Proceed to next gate." if ok else "Fix evidence and rerun review.",
        )

    if "required_any" in criterion:
        all_failures: list[str] = []
        for option in criterion["required_any"]:
            ok, failures = _matches(payload, option)
            if ok:
                return ApprovalGate(
                    id=criterion["id"],
                    title=criterion["title"],
                    status="passed",
                    source=str(path),
                    evidence=[f"{key}={_get_nested(payload, key)!r}" for key in option],
                    next_action=criterion.get("note", "Proceed to next gate."),
                )
            all_failures.extend(failures)
        return ApprovalGate(
            id=criterion["id"],
            title=criterion["title"],
            status="blocked",
            source=str(path),
            blocked_reasons=all_failures,
            next_action="Fix safety gate result or rerun final live runner safety spec gate.",
        )

    return ApprovalGate(
        id=criterion["id"],
        title=criterion["title"],
        status="blocked",
        source=str(path),
        blocked_reasons=["criterion has no required condition"],
    )


def build_local_evidence_finalization_safety_spec_approval(
    repo_root: str | Path = ".",
) -> dict[str, Any]:
    repo = Path(repo_root)
    gates = [evaluate_approval_gate(repo, criterion) for criterion in SAFETY_SPEC_APPROVAL_CRITERIA]

    passed = [gate for gate in gates if gate.status == "passed"]
    blocked = [gate for gate in gates if gate.status in {"blocked", "missing", "invalid_json"}]

    ready_for_safety_spec_approval = len(passed) == len(gates)
    status = "ready_for_human_safety_spec_approval" if ready_for_safety_spec_approval else "blocked"

    return {
        "task": "local_evidence_finalization_safety_spec_approval",
        "generated_at": _now(),
        "repo_root": str(repo),
        "status": status,
        "pr64_context": PR64_CONTEXT,
        "approval_gates": [gate.to_dict() for gate in gates],
        "counts": {
            "passed": len(passed),
            "blocked": len(blocked),
            "total": len(gates),
        },
        "required_review_files": REQUIRED_REVIEW_FILES,
        "implementation_pr_hard_gates": IMPLEMENTATION_PR_HARD_GATES,
        "decision": {
            "safety_spec_human_approval_can_start": ready_for_safety_spec_approval,
            "implementation_pr_can_start": False,
            "why_implementation_still_blocked": "This package only finalizes evidence for safety spec approval. Implementation requires separate human-approved PR.",
        },
        "next_actions": [
            "If blocked, complete local validation evidence and rerun local validation recorder/evidence review/safety spec gate.",
            "If ready_for_human_safety_spec_approval, open a human safety spec approval PR.",
            "Do not implement final live runner in this PR.",
        ],
        "safety": _safety(),
    }


def render_markdown(package: dict[str, Any]) -> str:
    lines = [
        "# HS-CAD Local Evidence Finalization + Safety Spec Approval",
        "",
        f"- Status: `{package['status']}`",
        f"- Safety spec human approval can start: `{package['decision']['safety_spec_human_approval_can_start']}`",
        f"- Implementation PR can start: `{package['decision']['implementation_pr_can_start']}`",
        "",
        "## Approval Gates",
        "",
    ]

    for gate in package["approval_gates"]:
        lines.append(f"### {gate['id']} — {gate['title']}")
        lines.append(f"- Status: `{gate['status']}`")
        lines.append(f"- Source: `{gate['source']}`")
        if gate["evidence"]:
            lines.append("- Evidence:")
            for item in gate["evidence"]:
                lines.append(f"  - {item}")
        if gate["blocked_reasons"]:
            lines.append("- Blocked reasons:")
            for item in gate["blocked_reasons"]:
                lines.append(f"  - {item}")
        lines.append(f"- Next action: {gate['next_action']}")
        lines.append("")

    lines += ["## Implementation PR Hard Gates", ""]
    lines.extend(f"- {item}" for item in package["implementation_pr_hard_gates"])

    lines += ["", "## Safety", ""]
    for key, value in package["safety"].items():
        lines.append(f"- `{key}`: `{value}`")

    return "\n".join(lines).rstrip() + "\n"


def build_human_approval_prompt(package: dict[str, Any]) -> str:
    return f"""너는 HS-CAD final live runner safety spec human reviewer다.

목표:
LOCAL_*.json, LOCAL_VALIDATION_RESULT_SUMMARY.json, LOCAL_VALIDATION_EVIDENCE_REVIEW.json, FINAL_LIVE_RUNNER_SAFETY_SPEC_GATE.json 증거를 보고 safety spec approval 가능 여부를 판단한다.

현재 상태:
- package status: {package['status']}
- safety spec approval can start: {package['decision']['safety_spec_human_approval_can_start']}
- implementation PR can start: {package['decision']['implementation_pr_can_start']}

중요:
이 단계는 구현 승인 단계가 아니다.
final live runner 구현은 별도 PR에서만 가능하다.

검토할 hard gates:
{chr(10).join(f"- {item}" for item in package['implementation_pr_hard_gates'])}
"""


def write_local_evidence_finalization_outputs(
    repo_root: str | Path = ".",
    *,
    out_dir: str | Path = "outputs/local_evidence_finalization_safety_spec_approval",
) -> dict[str, Any]:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    package = build_local_evidence_finalization_safety_spec_approval(repo_root=repo_root)

    package_json = out / "LOCAL_EVIDENCE_FINALIZATION_SAFETY_SPEC_APPROVAL.json"
    package_md = out / "LOCAL_EVIDENCE_FINALIZATION_SAFETY_SPEC_APPROVAL.md"
    human_prompt = out / "HUMAN_SAFETY_SPEC_APPROVAL_PROMPT.md"
    hard_gates_json = out / "IMPLEMENTATION_PR_HARD_GATES.json"

    package_json.write_text(json.dumps(package, ensure_ascii=False, indent=2), encoding="utf-8")
    package_md.write_text(render_markdown(package), encoding="utf-8")
    human_prompt.write_text(build_human_approval_prompt(package), encoding="utf-8")
    hard_gates_json.write_text(json.dumps(IMPLEMENTATION_PR_HARD_GATES, ensure_ascii=False, indent=2), encoding="utf-8")

    return {
        "status": package["status"],
        "out_dir": str(out),
        "package_json": str(package_json),
        "package_md": str(package_md),
        "human_prompt": str(human_prompt),
        "hard_gates_json": str(hard_gates_json),
        "safety": package["safety"],
    }
