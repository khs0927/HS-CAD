from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PR_STACK_CONTEXT = [
    {
        "pr": "#55",
        "branch": "integration/main-merge-readiness-decision",
        "url": "https://github.com/khs0927/HS-CAD/pull/55",
        "purpose": "Main merge readiness decision package",
        "reported_validation": "200 passed, 16 skipped; ruff core checks passed; decision status ready_for_human_main_merge_review",
        "status": "human_review_required",
    },
    {
        "pr": "#56",
        "branch": "integration/main-ready-review-only-pipeline",
        "url": "https://github.com/khs0927/HS-CAD/pull/56",
        "purpose": "Main-based review-only integration validation",
        "reported_validation": "206 passed, 16 skipped; compileall passed; CLI smoke passed; main-ready yes",
        "status": "human_review_required",
    },
    {
        "pr": "#57",
        "branch": "integration/main-merge-operator-review",
        "url": "unknown_or_local_context",
        "purpose": "Main merge operator review package",
        "reported_validation": "operator review package expected",
        "status": "optional_if_pr58_used_as_planning_base",
    },
    {
        "pr": "#58",
        "branch": "planning/post-main-local-validation-live-runner-safety",
        "url": "https://github.com/khs0927/HS-CAD/pull/58",
        "purpose": "Post-main local validation and final live runner safety planning",
        "reported_validation": "218 passed, 16 skipped; compileall passed; CLI smoke passed",
        "status": "human_review_required",
    },
]


POST_MERGE_LOCAL_VALIDATION_STEPS = [
    {
        "id": "post-merge-local-01",
        "title": "Copied DWG scan validation",
        "command": 'python -X utf8 -m src.main zwcad-copy-scan-validate --original-dwg "C:/cad/test/original.dwg" --working-copy-dwg "C:/cad/test_work/copy.dwg" --out-dir outputs/zwcad_copy_validation_live',
        "environment": "Windows + ZWCAD installed",
        "must_confirm": [
            "original_dwg_hash_before_recorded",
            "original_dwg_hash_after_unchanged",
            "working_copy_path_differs_from_original",
            "audit_log_written",
            "no_sendcommand_for_scan",
        ],
        "status": "post_merge_manual_only",
    },
    {
        "id": "post-merge-local-02",
        "title": "Copied DWG SaveAs validation",
        "command": 'python -X utf8 -m src.main zwcad-copy-saveas-validate --original-dwg "C:/cad/test/original.dwg" --working-copy-dwg "C:/cad/test_work/copy.dwg" --save-as-target "C:/cad/test_work/result.dwg" --out-dir outputs/zwcad_copy_saveas_validation_live --overwrite-copy',
        "environment": "Windows + ZWCAD installed",
        "must_confirm": [
            "save_as_target_differs_from_original",
            "original_dwg_hash_after_unchanged",
            "before_scan_written",
            "after_scan_written",
            "delta_report_written",
            "audit_log_written",
        ],
        "status": "post_merge_manual_only",
    },
    {
        "id": "post-merge-local-03",
        "title": "C:/xicad allowlist policy validation",
        "command": 'python -X utf8 -m src.main xicad-policy-candidates --xicad-root C:/xicad --out-dir outputs/xicad_policy_candidates_verify',
        "environment": "Windows + C:/xicad",
        "must_confirm": [
            "allowed_for_execution_false",
            "execution_allowed_aliases_empty",
            "unknown_aliases_blocked",
            "destructive_aliases_blocked",
            "policy_artifacts_written",
        ],
        "status": "post_merge_manual_only",
    },
    {
        "id": "post-merge-local-04",
        "title": "Phase 12 candidate guard only",
        "command": "python -X utf8 -m src.main hscad-analysis-phase12-manual-live-candidate --workspace outputs/phase10_11_domain_copy_verify --alias WAL --manual-live-flag --operator-approved --out-dir outputs/phase12_manual_live_candidate_verify",
        "environment": "Windows + copied DWG + allowlist artifacts",
        "must_confirm": [
            "candidate_created_or_blocked_with_reason",
            "execution_allowed_false",
            "sendcommand_allowed_false",
            "final_runner_guard_not_implemented",
            "original_dwg_not_mutated",
        ],
        "status": "post_merge_manual_only",
    },
]


@dataclass(frozen=True)
class HumanReviewGate:
    id: str
    title: str
    status: str
    evidence: list[str] = field(default_factory=list)
    blocked_reasons: list[str] = field(default_factory=list)
    human_action: str = ""

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
    }


def build_human_main_merge_review_gate(
    repo_root: str | Path = ".",
    *,
    post_main_safety_workspace: str | Path = "outputs/post_main_local_validation_live_runner_safety",
) -> dict[str, Any]:
    repo = Path(repo_root)
    workspace = Path(post_main_safety_workspace)

    gates: list[HumanReviewGate] = []

    post_main_bundle = workspace / "POST_MAIN_LOCAL_VALIDATION_LIVE_RUNNER_SAFETY_BUNDLE.json"
    post_main_payload = _load_json(post_main_bundle)

    gates.append(
        HumanReviewGate(
            id="human-gate:pr-stack-reviewed",
            title="PR #55~#58 stack requires human review",
            status="human_review_required",
            evidence=[f"{item['pr']} {item['branch']} {item['url']}" for item in PR_STACK_CONTEXT],
            human_action="Review GitHub PR diffs and confirm only review-only/plan-only/safety-guard scope is included.",
        )
    )

    gates.append(
        HumanReviewGate(
            id="human-gate:post-main-safety-bundle",
            title="Post-main local validation and live runner safety bundle exists",
            status="ok" if post_main_payload else "review_required",
            evidence=[str(post_main_bundle)] if post_main_payload else [],
            blocked_reasons=[] if post_main_payload else [f"missing:{post_main_bundle}"],
            human_action="If missing locally, use PR #58 report and docs/109~112 as evidence.",
        )
    )

    gates.append(
        HumanReviewGate(
            id="human-gate:main-merge-scope",
            title="Main merge scope is limited",
            status="human_review_required",
            evidence=[
                "Allowed: review-only pipeline, plan-only bridge, copied-DWG planning, safety docs",
                "Disallowed: final live runner, SendCommand, XiCAD alias execution, original DWG mutation",
            ],
            human_action="Reject merge if any live execution capability is included.",
        )
    )

    gates.append(
        HumanReviewGate(
            id="human-gate:post-merge-local-validation",
            title="Local validation remains post-merge manual-only",
            status="ok",
            evidence=[step["id"] for step in POST_MERGE_LOCAL_VALIDATION_STEPS],
            human_action="Do not require live ZWCAD validation for review-only main merge unless repository policy says so.",
        )
    )

    return {
        "task": "human_main_merge_review_gate",
        "generated_at": _now(),
        "repo_root": str(repo),
        "post_main_safety_workspace": str(workspace),
        "status": "ready_for_human_main_merge_review",
        "pr_stack_context": PR_STACK_CONTEXT,
        "gates": [gate.to_dict() for gate in gates],
        "main_merge_allowed_scope": [
            "review-only analysis pipeline",
            "plan-only Domain Rule bridge",
            "copied-DWG validation planning",
            "manual live candidate guard",
            "safety policy docs",
            "main-ready validation helpers",
            "post-main planning docs",
        ],
        "main_merge_disallowed_scope": [
            "final live runner",
            "ZWCAD COM SendCommand execution",
            "XiCAD alias execution",
            "Domain Rule Command Plan execution",
            "copied-DWG live validation in merge step",
            "original DWG mutation",
            "automatic operator approval",
        ],
        "pre_merge_validation_commands": [
            "git fetch origin",
            "git switch integration/main-ready-review-only-pipeline",
            "git pull --ff-only",
            "python -X utf8 -m compileall -q src tests",
            "python -X utf8 -m pytest -q",
            "python -X utf8 -m src.main --help",
            "python -X utf8 -m src.main hscad-main-merge-readiness-decision --out-dir outputs/human_main_merge_review_decision",
        ],
        "optional_validation_commands": [
            "python -X utf8 -m ruff check src tests --select E9,F63,F7,F82,F821",
            "python -X utf8 -m src.main hscad-main-merge-operator-review --repo-root . --pr56-workspace outputs/pr55_main_ready_review_only_validation --out-dir outputs/main_merge_operator_review",
            "python -X utf8 -m src.main hscad-post-main-local-validation-plan --repo-root . --operator-review-workspace outputs/main_merge_operator_review --out-dir outputs/post_main_local_validation_live_runner_safety",
        ],
        "post_merge_local_validation_steps": POST_MERGE_LOCAL_VALIDATION_STEPS,
        "final_live_runner_next_step": {
            "status": "deferred",
            "next_branch": "design/final-live-runner-safety-spec",
            "must_not_implement_runner_yet": True,
            "required_first": [
                "main merge human approval",
                "post-main local copied-DWG validation",
                "C:/xicad allowlist validation",
                "safety spec PR",
                "risk register review",
            ],
        },
        "safety": _safety(),
    }


def render_human_review_markdown(package: dict[str, Any]) -> str:
    lines = [
        "# HS-CAD Human Main Merge Review Gate",
        "",
        "## Summary",
        "",
        f"- Status: `{package['status']}`",
        "- This package does not merge main.",
        "- A human reviewer must decide whether to merge review-only / plan-only / safety-guard scope.",
        "",
        "## PR Stack Context",
        "",
    ]
    for item in package["pr_stack_context"]:
        lines.append(f"- `{item['pr']}` / `{item['branch']}`: {item['purpose']} — {item['url']}")

    lines += ["", "## Human Gates", ""]
    for gate in package["gates"]:
        lines.append(f"### {gate['id']}")
        lines.append("")
        lines.append(f"- Title: {gate['title']}")
        lines.append(f"- Status: `{gate['status']}`")
        if gate["blocked_reasons"]:
            lines.append(f"- Blocked reasons: {', '.join(gate['blocked_reasons'])}")
        lines.append(f"- Human action: {gate['human_action']}")
        lines.append("")

    lines += ["## Pre-merge Validation Commands", ""]
    for command in package["pre_merge_validation_commands"]:
        lines.append("```powershell")
        lines.append(command)
        lines.append("```")

    lines += ["", "## Allowed Scope", ""]
    lines.extend(f"- {item}" for item in package["main_merge_allowed_scope"])

    lines += ["", "## Disallowed Scope", ""]
    lines.extend(f"- {item}" for item in package["main_merge_disallowed_scope"])

    lines += ["", "## Post-merge Local Validation", ""]
    for step in package["post_merge_local_validation_steps"]:
        lines.append(f"- `{step['id']}`: {step['title']} / `{step['status']}`")

    lines += ["", "## Safety", ""]
    for key, value in package["safety"].items():
        lines.append(f"- `{key}`: `{value}`")

    return "\n".join(lines).rstrip() + "\n"


def build_human_operator_prompt(package: dict[str, Any]) -> str:
    return f"""너는 HS-CAD human main merge reviewer다.

목표:
PR #55~#58을 검토하고 main 병합 여부를 판단한다.

병합 허용 범위:
{chr(10).join(f"- {item}" for item in package["main_merge_allowed_scope"])}

병합 금지 범위:
{chr(10).join(f"- {item}" for item in package["main_merge_disallowed_scope"])}

필수 검증:
{chr(10).join(f"- {cmd}" for cmd in package["pre_merge_validation_commands"])}

중요:
- 이 판단은 자동 병합이 아니다.
- main에 직접 push하지 않는다.
- final live runner를 구현하지 않는다.
- Windows/ZWCAD local validation은 main 병합 후 수동 단계다.
"""


def build_post_merge_validation_prompt(package: dict[str, Any]) -> str:
    lines = [
        "너는 HS-CAD post-merge local validation agent다.",
        "",
        "이 작업은 main 병합 후 Windows/ZWCAD/C:/xicad 로컬 환경에서만 수동 실행한다.",
        "원본 DWG는 절대 수정하지 말고 copied DWG만 사용한다.",
        "final live runner는 구현하지 않는다.",
        "",
        "검증 순서:",
        "",
    ]
    for idx, step in enumerate(package["post_merge_local_validation_steps"], start=1):
        lines.append(f"{idx}. {step['title']}")
        lines.append(f"   환경: {step['environment']}")
        lines.append(f"   명령: {step['command']}")
        lines.append("   확인:")
        for item in step["must_confirm"]:
            lines.append(f"   - {item}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def write_human_main_merge_review_outputs(
    repo_root: str | Path = ".",
    *,
    post_main_safety_workspace: str | Path = "outputs/post_main_local_validation_live_runner_safety",
    out_dir: str | Path = "outputs/human_main_merge_review_gate",
) -> dict[str, Any]:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    package = build_human_main_merge_review_gate(
        repo_root=repo_root,
        post_main_safety_workspace=post_main_safety_workspace,
    )

    paths = {
        "package_json": out / "HUMAN_MAIN_MERGE_REVIEW_GATE.json",
        "package_md": out / "HUMAN_MAIN_MERGE_REVIEW_GATE.md",
        "operator_prompt": out / "HUMAN_MAIN_MERGE_OPERATOR_PROMPT.md",
        "post_merge_prompt": out / "POST_MERGE_LOCAL_VALIDATION_PROMPT.md",
        "post_merge_commands": out / "POST_MERGE_LOCAL_VALIDATION_COMMANDS.json",
        "final_live_runner_guard": out / "FINAL_LIVE_RUNNER_DEFERRED_GUARD.json",
    }

    paths["package_json"].write_text(json.dumps(package, ensure_ascii=False, indent=2), encoding="utf-8")
    paths["package_md"].write_text(render_human_review_markdown(package), encoding="utf-8")
    paths["operator_prompt"].write_text(build_human_operator_prompt(package), encoding="utf-8")
    paths["post_merge_prompt"].write_text(build_post_merge_validation_prompt(package), encoding="utf-8")
    paths["post_merge_commands"].write_text(
        json.dumps(package["post_merge_local_validation_steps"], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    paths["final_live_runner_guard"].write_text(
        json.dumps(package["final_live_runner_next_step"], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    return {
        "status": package["status"],
        "out_dir": str(out),
        **{key: str(value) for key, value in paths.items()},
        "safety": package["safety"],
    }
