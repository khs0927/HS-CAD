from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PR53_CONTEXT = {
    "branch": "integration/main-readiness-local-validation-plan",
    "pr_url": "https://github.com/khs0927/HS-CAD/pull/53",
    "title": "Main Readiness Local Validation Planner",
    "reported_tests": {
        "targeted": "tests/test_main_readiness_local_validation_planner.py: 3 passed",
        "full_pytest": "194 passed, 16 skipped",
        "cli_help": "python -X utf8 -m src.main --help passed",
        "cli_smoke": "hscad-main-readiness-plan passed",
    },
    "reported_status": "ready_for_main_readiness_review",
    "reported_safety": {
        "final_live_runner_implemented": False,
        "sendcommand_allowed_by_default": False,
        "cad_execution_allowed_by_default": False,
        "local_only_validation_required_before_live_runner": True,
    },
}


FINAL_REVIEW_REQUIRED_REPORTS = [
    "docs/91_final_analysis_cli_registration_report.md",
    "docs/92_final_analysis_worker_manifest_registration_report.md",
    "docs/93_final_review_pipeline_readiness_report.md",
    "docs/95_main_readiness_local_validation_report.md",
    "docs/90_final_live_runner_deferred_safety_policy.md",
]


FINAL_REVIEW_REQUIRED_COMMANDS = [
    "hscad-analysis-phase3-bind",
    "hscad-analysis-phase4-bridge",
    "hscad-analysis-phase5-domain-bridge",
    "hscad-analysis-phase6-domain-adapter",
    "hscad-analysis-phase7-9-review-bundle",
    "hscad-analysis-phase10-11-domain-copy",
    "hscad-analysis-phase12-manual-live-candidate",
    "hscad-final-todo-readiness",
    "hscad-main-readiness-plan",
]


LOCAL_ONLY_VALIDATION_STEPS = [
    {
        "id": "local-01-copy-scan",
        "title": "Copied DWG scan validation",
        "environment": "Windows + ZWCAD installed",
        "command": 'python -X utf8 -m src.main zwcad-copy-scan-validate --original-dwg "C:/cad/test/original.dwg" --working-copy-dwg "C:/cad/test_work/copy.dwg" --out-dir outputs/zwcad_copy_validation_live',
        "required_confirmations": [
            "original_dwg_hash_before_recorded",
            "original_dwg_hash_after_unchanged",
            "working_copy_path_differs_from_original",
            "audit_log_written",
            "no_sendcommand_for_scan",
        ],
        "status": "local_only_pending",
    },
    {
        "id": "local-02-copy-saveas",
        "title": "Copied DWG SaveAs validation",
        "environment": "Windows + ZWCAD installed",
        "command": 'python -X utf8 -m src.main zwcad-copy-saveas-validate --original-dwg "C:/cad/test/original.dwg" --working-copy-dwg "C:/cad/test_work/copy.dwg" --save-as-target "C:/cad/test_work/result.dwg" --out-dir outputs/zwcad_copy_saveas_validation_live --overwrite-copy',
        "required_confirmations": [
            "save_as_target_differs_from_original",
            "original_dwg_hash_after_unchanged",
            "before_scan_written",
            "after_scan_written",
            "delta_report_written",
            "audit_log_written",
        ],
        "status": "local_only_pending",
    },
    {
        "id": "local-03-xicad-policy-candidates",
        "title": "XiCAD policy candidate generation from C:/xicad",
        "environment": "Windows + local C:/xicad",
        "command": "python -X utf8 -m src.main xicad-policy-candidates --xicad-root C:/xicad --out-dir outputs/xicad_policy_candidates_verify",
        "required_confirmations": [
            "allowed_for_execution_false",
            "execution_allowed_aliases_empty",
            "unknown_aliases_blocked",
            "destructive_aliases_blocked",
            "policy_artifacts_written",
        ],
        "status": "local_only_pending",
    },
    {
        "id": "local-04-phase12-candidate-guard",
        "title": "Phase 12 manual live candidate guard only",
        "environment": "Windows + copied DWG + allowlist artifacts",
        "command": "python -X utf8 -m src.main hscad-analysis-phase12-manual-live-candidate --workspace outputs/phase10_11_domain_copy_verify --alias WAL --manual-live-flag --operator-approved --out-dir outputs/phase12_manual_live_candidate_verify",
        "required_confirmations": [
            "candidate_created_or_blocked_with_reason",
            "execution_allowed_false",
            "sendcommand_allowed_false",
            "final_runner_guard_not_implemented",
            "original_dwg_not_mutated",
        ],
        "status": "local_only_pending",
    },
]


@dataclass(frozen=True)
class GateCheck:
    id: str
    title: str
    status: str
    evidence: list[str] = field(default_factory=list)
    blocked_reasons: list[str] = field(default_factory=list)
    next_step: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _exists(path: Path) -> bool:
    return path.exists()


def _json_loadable(path: Path) -> bool:
    if not path.exists() or path.suffix.lower() != ".json":
        return False
    try:
        json.loads(path.read_text(encoding="utf-8"))
        return True
    except Exception:
        return False


def _safety() -> dict[str, Any]:
    return {
        "main_direct_push_allowed": False,
        "source_mutation_allowed": False,
        "original_dwg_mutation_allowed": False,
        "cad_execution_allowed_by_default": False,
        "zwcad_com_allowed_by_default": False,
        "sendcommand_allowed_by_default": False,
        "xicad_alias_execution_allowed_by_default": False,
        "final_live_runner_implemented": False,
        "local_only_validation_required_before_live_runner": True,
        "main_merge_requires_human_review": True,
    }


def build_post_pr53_main_merge_plan(
    repo_root: str | Path = ".",
    main_readiness_workspace: str | Path = "outputs/main_readiness_local_validation",
) -> dict[str, Any]:
    repo = Path(repo_root)
    workspace = Path(main_readiness_workspace)

    checks: list[GateCheck] = []
    warnings: list[str] = []

    required_docs_missing = [path for path in FINAL_REVIEW_REQUIRED_REPORTS if not (repo / path).exists()]
    checks.append(
        GateCheck(
            id="gate:required-final-reports",
            title="Final registration/readiness reports are present",
            status="ok" if not required_docs_missing else "blocked",
            evidence=[path for path in FINAL_REVIEW_REQUIRED_REPORTS if (repo / path).exists()],
            blocked_reasons=[f"missing:{path}" for path in required_docs_missing],
            next_step="Generate missing docs/91~95 reports before main readiness review." if required_docs_missing else "Ready.",
        )
    )

    plan_json = workspace / "MAIN_READINESS_LOCAL_VALIDATION_PLAN.json"
    local_todo_json = workspace / "LOCAL_ONLY_VALIDATION_TODO.json"

    checks.append(
        GateCheck(
            id="gate:pr53-artifacts",
            title="PR #53 main readiness artifacts exist",
            status="ok" if plan_json.exists() and local_todo_json.exists() and _json_loadable(plan_json) and _json_loadable(local_todo_json) else "partial",
            evidence=[str(path) for path in [plan_json, local_todo_json] if path.exists()],
            blocked_reasons=[] if plan_json.exists() and local_todo_json.exists() else ["missing_pr53_output_artifacts"],
            next_step="Rerun hscad-main-readiness-plan if artifacts are missing.",
        )
    )

    checks.append(
        GateCheck(
            id="gate:pr53-reported-tests",
            title="PR #53 reported tests accepted",
            status="ok",
            evidence=[
                PR53_CONTEXT["reported_tests"]["targeted"],
                PR53_CONTEXT["reported_tests"]["full_pytest"],
                PR53_CONTEXT["reported_tests"]["cli_help"],
                PR53_CONTEXT["reported_tests"]["cli_smoke"],
            ],
            next_step="Re-run full pytest on final integration branch before main merge.",
        )
    )

    safety_failures = [
        key for key, value in PR53_CONTEXT["reported_safety"].items()
        if (key in {"final_live_runner_implemented", "sendcommand_allowed_by_default", "cad_execution_allowed_by_default"} and value is not False)
        or (key == "local_only_validation_required_before_live_runner" and value is not True)
    ]
    checks.append(
        GateCheck(
            id="gate:pr53-safety-flags",
            title="PR #53 safety flags are conservative",
            status="ok" if not safety_failures else "blocked",
            evidence=[f"{key}={value}" for key, value in PR53_CONTEXT["reported_safety"].items()],
            blocked_reasons=[f"unsafe:{key}" for key in safety_failures],
            next_step="Fix safety flags if any are unsafe." if safety_failures else "Ready.",
        )
    )

    main_merge_recommendation = "not_ready"
    if all(check.status == "ok" for check in checks):
        main_merge_recommendation = "ready_for_human_main_readiness_review"
    elif any(check.status == "blocked" for check in checks):
        main_merge_recommendation = "blocked"
    else:
        main_merge_recommendation = "partial"

    return {
        "task": "post_pr53_main_merge_local_validation",
        "generated_at": _now(),
        "repo_root": str(repo),
        "main_readiness_workspace": str(workspace),
        "pr53_context": PR53_CONTEXT,
        "status": main_merge_recommendation,
        "gate_checks": [check.to_dict() for check in checks],
        "final_review_required_commands": FINAL_REVIEW_REQUIRED_COMMANDS,
        "local_only_validation_steps": LOCAL_ONLY_VALIDATION_STEPS,
        "main_merge_human_checklist": [
            "Confirm PR #49 and PR #53 are merged or approved in the expected stack.",
            "Confirm reg/final-analysis-cli-registration is merged.",
            "Confirm reg/final-analysis-worker-manifest is merged.",
            "Confirm integration/final-review-pipeline-readiness is merged or green.",
            "Confirm full pytest passes on the final integration branch.",
            "Confirm src.main --help lists all review-only commands.",
            "Confirm no outputs/scratch/dwg/dxf/zip/cache files are committed.",
            "Confirm final live runner remains deferred.",
            "Confirm local-only validation TODOs are not treated as blockers for review-only main merge unless policy requires them.",
        ],
        "final_live_runner_gate": {
            "status": "deferred",
            "can_implement_now": False,
            "required_before_implementation": [
                "local_only_validation_steps_completed",
                "original_dwg_hash_unchanged_verified",
                "copied_dwg_validation_successful",
                "xicad_allowlist_candidate_verified",
                "manual one-command live candidate reviewed",
                "separate final live runner safety design PR",
            ],
        },
        "warnings": warnings,
        "safety": _safety(),
    }


def render_post_pr53_markdown(plan: dict[str, Any]) -> str:
    lines = [
        "# HS-CAD Post-PR53 Main Merge & Local-only Validation Plan",
        "",
        "## Summary",
        "",
        f"- PR #53: {plan['pr53_context']['pr_url']}",
        f"- Branch: `{plan['pr53_context']['branch']}`",
        f"- Status: `{plan['status']}`",
        "",
        "## PR #53 Reported Validation",
        "",
    ]
    for key, value in plan["pr53_context"]["reported_tests"].items():
        lines.append(f"- `{key}`: {value}")

    lines += ["", "## Gate Checks", ""]
    for check in plan["gate_checks"]:
        lines.append(f"- `{check['id']}` / `{check['status']}`: {check['title']}")
        if check["blocked_reasons"]:
            lines.append(f"  - blocked: {', '.join(check['blocked_reasons'])}")

    lines += ["", "## Local-only Validation Steps", ""]
    for step in plan["local_only_validation_steps"]:
        lines.append(f"### {step['id']}")
        lines.append("")
        lines.append(f"- Title: {step['title']}")
        lines.append(f"- Environment: {step['environment']}")
        lines.append(f"- Status: `{step['status']}`")
        lines.append(f"- Command: `{step['command']}`")
        lines.append("")

    lines += ["## Main Merge Human Checklist", ""]
    lines.extend(f"- {item}" for item in plan["main_merge_human_checklist"])

    lines += ["", "## Final Live Runner Gate", ""]
    gate = plan["final_live_runner_gate"]
    lines.append(f"- Status: `{gate['status']}`")
    lines.append(f"- Can implement now: `{gate['can_implement_now']}`")
    for item in gate["required_before_implementation"]:
        lines.append(f"- Required: {item}")

    lines += ["", "## Safety", ""]
    for key, value in plan["safety"].items():
        lines.append(f"- `{key}`: `{value}`")

    return "\n".join(lines).rstrip() + "\n"


def write_post_pr53_outputs(
    repo_root: str | Path = ".",
    main_readiness_workspace: str | Path = "outputs/main_readiness_local_validation",
    *,
    out_dir: str | Path = "outputs/post_pr53_main_merge_local_validation",
) -> dict[str, Any]:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    plan = build_post_pr53_main_merge_plan(repo_root=repo_root, main_readiness_workspace=main_readiness_workspace)

    plan_json = out / "POST_PR53_MAIN_MERGE_LOCAL_VALIDATION_PLAN.json"
    plan_md = out / "POST_PR53_MAIN_MERGE_LOCAL_VALIDATION_PLAN.md"
    local_steps_json = out / "POST_PR53_LOCAL_ONLY_VALIDATION_STEPS.json"
    merge_checklist_json = out / "POST_PR53_MAIN_MERGE_HUMAN_CHECKLIST.json"

    plan_json.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
    plan_md.write_text(render_post_pr53_markdown(plan), encoding="utf-8")
    local_steps_json.write_text(json.dumps(plan["local_only_validation_steps"], ensure_ascii=False, indent=2), encoding="utf-8")
    merge_checklist_json.write_text(json.dumps(plan["main_merge_human_checklist"], ensure_ascii=False, indent=2), encoding="utf-8")

    return {
        "status": plan["status"],
        "out_dir": str(out),
        "plan_json": str(plan_json),
        "plan_md": str(plan_md),
        "local_steps_json": str(local_steps_json),
        "merge_checklist_json": str(merge_checklist_json),
        "safety": plan["safety"],
    }
