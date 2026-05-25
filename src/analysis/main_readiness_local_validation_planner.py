from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


MAIN_READINESS_REQUIRED_DOCS = [
    "docs/91_final_analysis_cli_registration_report.md",
    "docs/92_final_analysis_worker_manifest_registration_report.md",
    "docs/93_final_review_pipeline_readiness_report.md",
    "docs/90_final_live_runner_deferred_safety_policy.md",
]

MAIN_READINESS_REQUIRED_FILES = [
    "src/main.py",
    "config/worker_manifest.json",
]

EXPECTED_FINAL_REVIEW_ARTIFACTS = [
    "PHASE3_REAL_DATA_BINDING_REPORT.json",
    "PHASE4_DECISION_BRIDGE_PACKAGE.json",
    "PHASE5_DOMAIN_RULE_INPUT_PACKAGE.json",
    "DOMAIN_RULE_DECISION_INPUT_FROM_PHASE6.json",
    "PHASE7_DOMAIN_DECISION_PACKAGE.json",
    "PHASE8_REVIEW_GATE_CHAIN.json",
    "PHASE9_PIPELINE_READINESS_SUMMARY.json",
    "PHASE10_DOMAIN_DECISION_CONNECTOR.json",
    "PHASE11_COPIED_DWG_VALIDATION_BRIDGE.json",
    "PHASE12_MANUAL_LIVE_EXECUTION_CANDIDATE.json",
    "FINAL_TODO_INTEGRATION_READINESS.json",
]


@dataclass(frozen=True)
class ReadinessCheck:
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
    }


def build_main_readiness_plan(
    repo_root: str | Path = ".",
    final_review_workspace: str | Path = "outputs/final_review_pipeline_verify",
) -> dict[str, Any]:
    repo = Path(repo_root)
    workspace = Path(final_review_workspace)

    checks: list[ReadinessCheck] = []
    warnings: list[str] = []

    missing_docs = [path for path in MAIN_READINESS_REQUIRED_DOCS if not (repo / path).exists()]
    checks.append(
        ReadinessCheck(
            id="main-readiness:required-docs",
            title="Required final readiness docs exist",
            status="ok" if not missing_docs else "blocked",
            evidence=[path for path in MAIN_READINESS_REQUIRED_DOCS if (repo / path).exists()],
            blocked_reasons=[f"missing:{path}" for path in missing_docs],
            next_step="Create or verify docs/91, docs/92, docs/93 before main readiness." if missing_docs else "Ready.",
        )
    )

    missing_files = [path for path in MAIN_READINESS_REQUIRED_FILES if not (repo / path).exists()]
    checks.append(
        ReadinessCheck(
            id="main-readiness:required-files",
            title="Required integration files exist",
            status="ok" if not missing_files else "blocked",
            evidence=[path for path in MAIN_READINESS_REQUIRED_FILES if (repo / path).exists()],
            blocked_reasons=[f"missing:{path}" for path in missing_files],
            next_step="Confirm src/main.py and config/worker_manifest.json exist." if missing_files else "Ready.",
        )
    )

    artifact_records = []
    missing_artifacts = []
    json_warnings = []
    for name in EXPECTED_FINAL_REVIEW_ARTIFACTS:
        path = workspace / name
        exists = path.exists()
        json_ok = _json_loadable(path)
        artifact_records.append(
            {
                "name": name,
                "path": str(path),
                "exists": exists,
                "json_loadable": json_ok,
                "size_bytes": path.stat().st_size if exists else 0,
            }
        )
        if not exists:
            missing_artifacts.append(name)
        elif path.suffix.lower() == ".json" and not json_ok:
            json_warnings.append(name)

    checks.append(
        ReadinessCheck(
            id="main-readiness:final-review-artifacts",
            title="Final review-only pipeline artifacts exist",
            status="ok" if not missing_artifacts and not json_warnings else "partial",
            evidence=[item["name"] for item in artifact_records if item["exists"]],
            blocked_reasons=[f"missing:{name}" for name in missing_artifacts] + [f"json_warning:{name}" for name in json_warnings],
            next_step="Run final-review synthetic E2E chain again if artifacts are missing.",
        )
    )

    local_only_todos = [
        {
            "id": "local:zwcad-copy-scan-validate",
            "title": "Run ZWCAD copied-DWG scan validation",
            "environment": "Windows + ZWCAD installed",
            "status": "local_only_pending",
            "command_template": 'python -X utf8 -m src.main zwcad-copy-scan-validate --original-dwg "C:/cad/test/original.dwg" --working-copy-dwg "C:/cad/test_work/copy.dwg" --out-dir outputs/zwcad_copy_validation_live',
            "must_confirm": [
                "original_dwg_hash_unchanged",
                "working_copy_path_differs_from_original",
                "no_sendcommand_for_scan",
                "audit_log_written",
            ],
        },
        {
            "id": "local:zwcad-copy-saveas-validate",
            "title": "Run ZWCAD copied-DWG SaveAs validation",
            "environment": "Windows + ZWCAD installed",
            "status": "local_only_pending",
            "command_template": 'python -X utf8 -m src.main zwcad-copy-saveas-validate --original-dwg "C:/cad/test/original.dwg" --working-copy-dwg "C:/cad/test_work/copy.dwg" --save-as-target "C:/cad/test_work/result.dwg" --out-dir outputs/zwcad_copy_saveas_validation_live --overwrite-copy',
            "must_confirm": [
                "save_as_target_differs_from_original",
                "original_dwg_hash_unchanged",
                "delta_report_written",
                "audit_log_written",
            ],
        },
        {
            "id": "local:xicad-policy-candidates",
            "title": "Generate XiCAD policy candidates from C:/xicad",
            "environment": "Windows + local C:/xicad",
            "status": "local_only_pending",
            "command_template": 'python -X utf8 -m src.main xicad-policy-candidates --xicad-root C:/xicad --out-dir outputs/xicad_policy_candidates_verify',
            "must_confirm": [
                "allowed_for_execution_false",
                "execution_allowed_aliases_empty",
                "unknown_aliases_blocked",
                "destructive_aliases_blocked",
            ],
        },
        {
            "id": "local:manual-live-candidate-only",
            "title": "Prepare one manual live candidate without final runner",
            "environment": "Windows + copied DWG + allowlist + operator approval",
            "status": "deferred_until_local_checks_pass",
            "command_template": "Do not run final runner. Only run Phase 12 candidate guard.",
            "must_confirm": [
                "final_runner_not_implemented",
                "execution_allowed_false",
                "sendcommand_allowed_false",
                "manual_live_candidate_documented_only",
            ],
        },
    ]

    main_merge_todos = [
        {
            "id": "merge:verify-pr-stack",
            "title": "Verify all PRs from Phase 3 through final readiness are green",
            "status": "required",
        },
        {
            "id": "merge:run-full-pytest",
            "title": "Run full pytest from integration/final-review-pipeline-readiness",
            "status": "required",
        },
        {
            "id": "merge:run-cli-help",
            "title": "Run src.main --help and confirm all review-only commands",
            "status": "required",
        },
        {
            "id": "merge:no-output-pollution",
            "title": "Confirm no outputs/scratch/dwg/dxf/zip/cache are committed",
            "status": "required",
        },
        {
            "id": "merge:defer-live-runner",
            "title": "Keep final live runner deferred",
            "status": "required",
        },
    ]

    if missing_docs or missing_files:
        overall = "blocked"
    elif missing_artifacts:
        overall = "partial"
    else:
        overall = "ready_for_main_readiness_review"

    return {
        "task": "main_readiness_local_validation_planner",
        "generated_at": _now(),
        "repo_root": str(repo),
        "final_review_workspace": str(workspace),
        "status": overall,
        "checks": [item.to_dict() for item in checks],
        "final_review_artifacts": artifact_records,
        "local_only_todos": local_only_todos,
        "main_merge_todos": main_merge_todos,
        "warnings": warnings,
        "safety": _safety(),
    }


def render_main_readiness_markdown(plan: dict[str, Any]) -> str:
    lines = [
        "# HS-CAD Main Readiness & Local-only Validation Planner",
        "",
        "## Summary",
        "",
        f"- Repo root: `{plan['repo_root']}`",
        f"- Final review workspace: `{plan['final_review_workspace']}`",
        f"- Status: `{plan['status']}`",
        "",
        "## Readiness Checks",
        "",
    ]
    for check in plan["checks"]:
        lines.append(f"- `{check['id']}` / `{check['status']}`: {check['title']}")
        if check["blocked_reasons"]:
            lines.append(f"  - blocked: {', '.join(check['blocked_reasons'])}")

    lines += ["", "## Local-only TODOs", ""]
    for todo in plan["local_only_todos"]:
        lines.append(f"### {todo['id']}")
        lines.append("")
        lines.append(f"- Title: {todo['title']}")
        lines.append(f"- Environment: {todo['environment']}")
        lines.append(f"- Status: `{todo['status']}`")
        lines.append(f"- Command template: `{todo['command_template']}`")
        lines.append("")

    lines += ["## Main Merge TODOs", ""]
    for todo in plan["main_merge_todos"]:
        lines.append(f"- `{todo['id']}` / `{todo['status']}`: {todo['title']}")

    lines += ["", "## Safety", ""]
    for key, value in plan["safety"].items():
        lines.append(f"- `{key}`: `{value}`")

    return "\n".join(lines).rstrip() + "\n"


def write_main_readiness_plan_outputs(
    repo_root: str | Path = ".",
    final_review_workspace: str | Path = "outputs/final_review_pipeline_verify",
    *,
    out_dir: str | Path = "outputs/main_readiness_local_validation",
) -> dict[str, Any]:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    plan = build_main_readiness_plan(repo_root=repo_root, final_review_workspace=final_review_workspace)

    json_path = out / "MAIN_READINESS_LOCAL_VALIDATION_PLAN.json"
    md_path = out / "MAIN_READINESS_LOCAL_VALIDATION_PLAN.md"
    local_todo_path = out / "LOCAL_ONLY_VALIDATION_TODO.json"

    json_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(render_main_readiness_markdown(plan), encoding="utf-8")
    local_todo_path.write_text(json.dumps(plan["local_only_todos"], ensure_ascii=False, indent=2), encoding="utf-8")

    return {
        "status": plan["status"],
        "out_dir": str(out),
        "plan_json": str(json_path),
        "plan_md": str(md_path),
        "local_todo_json": str(local_todo_path),
        "safety": plan["safety"],
    }
