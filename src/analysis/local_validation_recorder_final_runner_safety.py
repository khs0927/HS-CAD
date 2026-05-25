from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PR59_CONTEXT = {
    "branch": "human/main-merge-review-gate",
    "pr_url": "https://github.com/khs0927/HS-CAD/pull/59",
    "title": "Add human main merge review gate",
    "base_branch": "planning/post-main-local-validation-live-runner-safety",
    "reported_validation": {
        "targeted": "tests/test_human_main_merge_review_gate.py: 3 passed",
        "compileall": "passed",
        "full_pytest": "227 passed, 16 skipped",
        "cli_smoke": "hscad-human-main-merge-review-gate passed",
        "ruff": "skipped because ruff was not globally installed in the local environment",
    },
    "reported_decision": "human review ready yes",
    "reported_safety": {
        "auto_merge_allowed": False,
        "main_direct_push_allowed": False,
        "this_package_merges_main": False,
        "human_review_required": True,
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
    },
    "remaining_todo": [
        "PR #55~#59 human approval and main merge decision",
        "After main merge, run local-only validation manually",
        "Validate C:/xicad allowlist aliases manually",
        "Review additional safety spec before any live runner work",
    ],
}


LOCAL_VALIDATION_EXPECTED_RESULTS = [
    {
        "id": "local-01-copied-dwg-scan",
        "title": "Copied DWG scan validation",
        "required_result_file": "LOCAL_01_COPIED_DWG_SCAN_RESULT.json",
        "required_fields": [
            "original_dwg",
            "working_copy_dwg",
            "original_hash_before",
            "original_hash_after",
            "original_hash_unchanged",
            "working_copy_differs_from_original",
            "audit_log_written",
            "sendcommand_used",
            "status",
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
        "required_result_file": "LOCAL_02_COPIED_DWG_SAVEAS_RESULT.json",
        "required_fields": [
            "original_dwg",
            "working_copy_dwg",
            "save_as_target",
            "save_as_target_differs_from_original",
            "original_hash_before",
            "original_hash_after",
            "original_hash_unchanged",
            "before_scan_written",
            "after_scan_written",
            "delta_report_written",
            "audit_log_written",
            "status",
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
        "required_result_file": "LOCAL_03_XICAD_POLICY_CANDIDATES_RESULT.json",
        "required_fields": [
            "xicad_root",
            "allowed_for_execution",
            "execution_allowed_aliases",
            "unknown_aliases_blocked",
            "destructive_aliases_blocked",
            "policy_artifacts_written",
            "status",
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
        "required_result_file": "LOCAL_04_PHASE12_CANDIDATE_GUARD_RESULT.json",
        "required_fields": [
            "candidate_created_or_blocked_with_reason",
            "execution_allowed",
            "sendcommand_allowed",
            "final_runner_implemented",
            "original_dwg_mutated",
            "status",
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


FINAL_LIVE_RUNNER_IMPLEMENTATION_GATES = [
    "PR #55~#59 human approval completed",
    "main merged with review-only / plan-only / safety-guard scope",
    "local-01 copied DWG scan validation passed",
    "local-02 copied DWG SaveAs validation passed",
    "local-03 C:/xicad policy candidate validation passed",
    "local-04 Phase 12 candidate guard validation passed",
    "safety spec PR approved",
    "risk register reviewed",
    "operator manual approval policy defined",
]


@dataclass(frozen=True)
class LocalValidationResult:
    id: str
    title: str
    status: str
    result_file: str
    missing_fields: list[str] = field(default_factory=list)
    failed_conditions: list[str] = field(default_factory=list)
    evidence: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        return {"__json_error__": str(exc)}


def _safety() -> dict[str, Any]:
    return {
        "this_bundle_executes_local_validation": False,
        "this_bundle_executes_cad": False,
        "this_bundle_calls_zwcad_com": False,
        "this_bundle_calls_sendcommand": False,
        "this_bundle_executes_xicad_alias": False,
        "this_bundle_implements_final_live_runner": False,
        "original_dwg_mutation_allowed": False,
        "final_live_runner_requires_separate_pr": True,
        "manual_copy_only_policy_required": True,
        "post_merge_local_validation_manual_only": True,
    }


def build_empty_local_validation_result_templates(out_dir: str | Path) -> dict[str, str]:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    written: dict[str, str] = {}

    for spec in LOCAL_VALIDATION_EXPECTED_RESULTS:
        template = {
            "id": spec["id"],
            "title": spec["title"],
            "status": "pending",
            "notes": "Fill this file after manually running the local-only validation command in Windows/ZWCAD/C:/xicad environment.",
        }
        for field_name in spec["required_fields"]:
            template.setdefault(field_name, None)
        path = out / spec["required_result_file"]
        path.write_text(json.dumps(template, ensure_ascii=False, indent=2), encoding="utf-8")
        written[spec["id"]] = str(path)

    return written


def evaluate_local_validation_results(result_dir: str | Path) -> list[LocalValidationResult]:
    base = Path(result_dir)
    results: list[LocalValidationResult] = []

    for spec in LOCAL_VALIDATION_EXPECTED_RESULTS:
        path = base / spec["required_result_file"]
        payload = _safe_load_json(path)
        if not payload:
            results.append(
                LocalValidationResult(
                    id=spec["id"],
                    title=spec["title"],
                    status="missing",
                    result_file=str(path),
                    missing_fields=spec["required_fields"],
                )
            )
            continue

        if "__json_error__" in payload:
            results.append(
                LocalValidationResult(
                    id=spec["id"],
                    title=spec["title"],
                    status="invalid_json",
                    result_file=str(path),
                    failed_conditions=[payload["__json_error__"]],
                )
            )
            continue

        missing_fields = [field_name for field_name in spec["required_fields"] if field_name not in payload]
        failed_conditions: list[str] = []
        for key, expected in spec["pass_conditions"].items():
            actual = payload.get(key)
            if actual != expected:
                failed_conditions.append(f"{key}: expected {expected!r}, got {actual!r}")

        status = "passed" if not missing_fields and not failed_conditions else "failed"
        results.append(
            LocalValidationResult(
                id=spec["id"],
                title=spec["title"],
                status=status,
                result_file=str(path),
                missing_fields=missing_fields,
                failed_conditions=failed_conditions,
                evidence={key: payload.get(key) for key in spec["pass_conditions"].keys()},
            )
        )

    return results


def build_local_validation_summary(result_dir: str | Path) -> dict[str, Any]:
    results = evaluate_local_validation_results(result_dir)
    passed = [item for item in results if item.status == "passed"]
    all_passed = len(passed) == len(LOCAL_VALIDATION_EXPECTED_RESULTS)

    return {
        "task": "local_validation_result_summary",
        "generated_at": _now(),
        "result_dir": str(Path(result_dir)),
        "status": "passed" if all_passed else "not_ready",
        "all_local_validations_passed": all_passed,
        "results": [item.to_dict() for item in results],
        "final_live_runner_spec_ready": all_passed,
        "final_live_runner_implementation_allowed": False,
        "implementation_gate_note": "Even if local validations pass, only safety spec PR can be prepared next; runner implementation remains separate.",
        "pr59_context": PR59_CONTEXT,
        "required_next_gates": FINAL_LIVE_RUNNER_IMPLEMENTATION_GATES,
        "safety": _safety(),
    }


def render_local_validation_summary_markdown(summary: dict[str, Any]) -> str:
    lines = [
        "# HS-CAD Local Validation Result Summary",
        "",
        f"- Status: `{summary['status']}`",
        f"- PR #59: {summary['pr59_context']['pr_url']}",
        f"- All local validations passed: `{summary['all_local_validations_passed']}`",
        f"- Final live runner spec ready: `{summary['final_live_runner_spec_ready']}`",
        f"- Final live runner implementation allowed: `{summary['final_live_runner_implementation_allowed']}`",
        "",
        "## Results",
        "",
    ]
    for item in summary["results"]:
        lines.append(f"### {item['id']}")
        lines.append("")
        lines.append(f"- Title: {item['title']}")
        lines.append(f"- Status: `{item['status']}`")
        if item["missing_fields"]:
            lines.append(f"- Missing fields: {', '.join(item['missing_fields'])}")
        if item["failed_conditions"]:
            lines.append("- Failed conditions:")
            for condition in item["failed_conditions"]:
                lines.append(f"  - {condition}")
        lines.append("")

    lines += ["## Required Next Gates", ""]
    lines.extend(f"- {gate}" for gate in summary["required_next_gates"])

    lines += ["", "## Safety", ""]
    for key, value in summary["safety"].items():
        lines.append(f"- `{key}`: `{value}`")

    return "\n".join(lines).rstrip() + "\n"


def write_local_validation_recorder_outputs(
    repo_root: str | Path = ".",
    *,
    result_dir: str | Path = "outputs/local_validation_results",
    out_dir: str | Path = "outputs/local_validation_recorder",
    create_templates: bool = True,
) -> dict[str, Any]:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    templates: dict[str, str] = {}
    if create_templates:
        templates = build_empty_local_validation_result_templates(result_dir)

    summary = build_local_validation_summary(result_dir)

    summary_json = out / "LOCAL_VALIDATION_RESULT_SUMMARY.json"
    summary_md = out / "LOCAL_VALIDATION_RESULT_SUMMARY.md"
    final_gate_json = out / "FINAL_LIVE_RUNNER_IMPLEMENTATION_GATE.json"
    pr59_context_json = out / "PR59_CONTEXT_FOR_LOCAL_VALIDATION.json"

    summary_json.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    summary_md.write_text(render_local_validation_summary_markdown(summary), encoding="utf-8")
    final_gate_json.write_text(
        json.dumps(
            {
                "status": "blocked" if not summary["all_local_validations_passed"] else "safety_spec_pr_ready",
                "final_live_runner_implementation_allowed": False,
                "required_next_gates": FINAL_LIVE_RUNNER_IMPLEMENTATION_GATES,
                "safety": summary["safety"],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    pr59_context_json.write_text(json.dumps(PR59_CONTEXT, ensure_ascii=False, indent=2), encoding="utf-8")

    return {
        "status": summary["status"],
        "result_dir": str(Path(result_dir)),
        "out_dir": str(out),
        "templates": templates,
        "summary_json": str(summary_json),
        "summary_md": str(summary_md),
        "final_gate_json": str(final_gate_json),
        "pr59_context_json": str(pr59_context_json),
        "safety": summary["safety"],
    }
