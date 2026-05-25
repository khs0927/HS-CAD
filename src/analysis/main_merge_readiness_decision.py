from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_POST_PR53_PLAN = "POST_PR53_MAIN_MERGE_LOCAL_VALIDATION_PLAN.json"

REQUIRED_MAIN_READINESS_DOCS = [
    "docs/90_final_live_runner_deferred_safety_policy.md",
    "docs/91_final_analysis_cli_registration_report.md",
    "docs/92_final_analysis_worker_manifest_registration_report.md",
    "docs/93_final_review_pipeline_readiness_report.md",
    "docs/95_main_readiness_local_validation_report.md",
    "docs/97_post_pr53_main_merge_local_validation_report.md",
    "docs/98_local_only_zwcad_xicad_validation_runbook.md",
]

REQUIRED_REVIEW_ONLY_COMMANDS = [
    "hscad-analysis-phase3-bind",
    "hscad-analysis-phase4-bridge",
    "hscad-analysis-phase5-domain-bridge",
    "hscad-analysis-phase6-domain-adapter",
    "hscad-analysis-phase7-9-review-bundle",
    "hscad-analysis-phase10-11-domain-copy",
    "hscad-analysis-phase12-manual-live-candidate",
    "hscad-final-todo-readiness",
    "hscad-main-readiness-plan",
    "hscad-post-pr53-main-readiness",
]


@dataclass(frozen=True)
class MainMergeGate:
    id: str
    title: str
    status: str
    evidence: list[str] = field(default_factory=list)
    blocked_reasons: list[str] = field(default_factory=list)
    required_action: str = ""

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
        "main_direct_push_allowed": False,
        "main_merge_requires_human_review": True,
        "source_mutation_allowed": False,
        "original_dwg_mutation_allowed": False,
        "cad_execution_allowed_by_default": False,
        "zwcad_com_allowed_by_default": False,
        "sendcommand_allowed_by_default": False,
        "xicad_alias_execution_allowed_by_default": False,
        "domain_rule_command_execution_allowed": False,
        "copied_dwg_live_validation_allowed_in_main_readiness": False,
        "final_live_runner_implemented": False,
        "final_live_runner_allowed": False,
        "local_only_validation_required_before_live_runner": True,
    }


def build_main_merge_readiness_decision(
    repo_root: str | Path = ".",
    post_pr53_workspace: str | Path = "outputs/post_pr53_main_merge_local_validation",
) -> dict[str, Any]:
    repo = Path(repo_root)
    workspace = Path(post_pr53_workspace)
    plan_path = workspace / DEFAULT_POST_PR53_PLAN

    gates: list[MainMergeGate] = []
    warnings: list[str] = []

    plan = _load_json(plan_path)
    if not plan:
        gates.append(
            MainMergeGate(
                id="gate:post-pr53-plan",
                title="Post-PR53 planning artifact exists",
                status="blocked",
                blocked_reasons=[f"missing:{plan_path}"],
                required_action="Run hscad-post-pr53-main-readiness first.",
            )
        )
    else:
        gates.append(
            MainMergeGate(
                id="gate:post-pr53-plan",
                title="Post-PR53 planning artifact exists",
                status="ok",
                evidence=[str(plan_path), str(plan.get("status", ""))],
                required_action="Review gate checks before main merge.",
            )
        )

    missing_docs = [doc for doc in REQUIRED_MAIN_READINESS_DOCS if not (repo / doc).exists()]
    gates.append(
        MainMergeGate(
            id="gate:readiness-docs",
            title="Required readiness and safety docs exist",
            status="ok" if not missing_docs else "blocked",
            evidence=[doc for doc in REQUIRED_MAIN_READINESS_DOCS if (repo / doc).exists()],
            blocked_reasons=[f"missing:{doc}" for doc in missing_docs],
            required_action="Create missing readiness docs before main merge." if missing_docs else "Ready.",
        )
    )

    safety = plan.get("safety", {}) if plan else {}
    unsafe_flags = []
    for key in [
        "source_mutation_allowed",
        "original_dwg_mutation_allowed",
        "cad_execution_allowed_by_default",
        "zwcad_com_allowed_by_default",
        "sendcommand_allowed_by_default",
        "xicad_alias_execution_allowed_by_default",
        "final_live_runner_implemented",
    ]:
        if safety.get(key) is True:
            unsafe_flags.append(key)

    gates.append(
        MainMergeGate(
            id="gate:safety-flags",
            title="Safety flags remain conservative",
            status="ok" if not unsafe_flags else "blocked",
            evidence=[f"{key}={safety.get(key)}" for key in sorted(safety.keys())],
            blocked_reasons=[f"unsafe_true:{key}" for key in unsafe_flags],
            required_action="Fix unsafe true safety flags." if unsafe_flags else "Ready.",
        )
    )

    post_gate_statuses = []
    if plan:
        post_gate_statuses = [str(item.get("status")) for item in plan.get("gate_checks", [])]
    blocked_post_gates = [status for status in post_gate_statuses if status == "blocked"]
    gates.append(
        MainMergeGate(
            id="gate:post-pr53-gates",
            title="Post-PR53 gates are not blocked",
            status="ok" if plan and not blocked_post_gates else "blocked",
            evidence=post_gate_statuses,
            blocked_reasons=["post_pr53_gate_blocked"] if blocked_post_gates or not plan else [],
            required_action="Resolve blocked Post-PR53 gates." if blocked_post_gates or not plan else "Ready.",
        )
    )

    final_live_gate = plan.get("final_live_runner_gate", {}) if plan else {}
    live_runner_ok = final_live_gate.get("can_implement_now") is False or not final_live_gate
    gates.append(
        MainMergeGate(
            id="gate:final-live-runner-deferred",
            title="Final live runner remains deferred",
            status="ok" if live_runner_ok else "blocked",
            evidence=[f"can_implement_now={final_live_gate.get('can_implement_now')}"],
            blocked_reasons=[] if live_runner_ok else ["final_live_runner_not_deferred"],
            required_action="Defer final live runner to separate safety PR.",
        )
    )

    if plan.get("status") in {"ready_for_human_main_readiness_review", "partial"}:
        warnings.append(
            "Main readiness may proceed to human review, but this package does not merge main automatically."
        )

    blocked = [gate for gate in gates if gate.status == "blocked"]
    if blocked:
        status = "blocked"
        recommendation = "Do not merge to main until blocked gates are resolved."
    else:
        status = "ready_for_human_main_merge_review"
        recommendation = (
            "Main merge can be reviewed by a human reviewer for review-only/plan-only pipeline only. "
            "Do not merge or implement final live runner in this step."
        )

    package = {
        "task": "main_merge_readiness_decision",
        "generated_at": _now(),
        "repo_root": str(repo),
        "post_pr53_workspace": str(workspace),
        "status": status,
        "recommendation": recommendation,
        "gates": [gate.to_dict() for gate in gates],
        "required_review_only_commands": REQUIRED_REVIEW_ONLY_COMMANDS,
        "main_merge_allowed_scope": [
            "review-only analysis pipeline",
            "plan-only Domain Rule bridge",
            "copied-DWG validation planning",
            "manual live candidate guard",
            "safety policy docs",
        ],
        "main_merge_disallowed_scope": [
            "final live runner",
            "ZWCAD COM SendCommand execution",
            "XiCAD alias execution",
            "Domain Rule Command Plan execution",
            "original DWG mutation",
            "automatic operator approval",
        ],
        "post_merge_local_validation": plan.get("local_only_validation_steps", []),
        "warnings": warnings,
        "safety": _safety(),
    }
    return package


def render_main_merge_decision_markdown(package: dict[str, Any]) -> str:
    lines = [
        "# HS-CAD Main Merge Readiness Decision",
        "",
        "## Summary",
        "",
        f"- Status: `{package['status']}`",
        f"- Recommendation: {package['recommendation']}",
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
        lines.append(f"- Required action: {gate['required_action']}")
        lines.append("")

    lines += ["## Allowed in Main Merge", ""]
    lines.extend(f"- {item}" for item in package["main_merge_allowed_scope"])

    lines += ["", "## Not Allowed in Main Merge", ""]
    lines.extend(f"- {item}" for item in package["main_merge_disallowed_scope"])

    lines += ["", "## Post-merge Local-only Validation", ""]
    if package["post_merge_local_validation"]:
        for step in package["post_merge_local_validation"]:
            lines.append(f"- `{step.get('id')}`: {step.get('title')} / `{step.get('status')}`")
    else:
        lines.append("- No local-only validation steps found in Post-PR53 plan.")

    lines += ["", "## Safety", ""]
    for key, value in package["safety"].items():
        lines.append(f"- `{key}`: `{value}`")

    return "\n".join(lines).rstrip() + "\n"


def build_main_merge_pr_body(package: dict[str, Any]) -> str:
    return f"""# Main Merge Readiness Review

## Summary

This PR/merge candidate is for the review-only and plan-only HS-CAD pipeline only.

Status: `{package['status']}`

Recommendation:

{package['recommendation']}

## Allowed scope

{chr(10).join(f"- {item}" for item in package["main_merge_allowed_scope"])}

## Disallowed scope

{chr(10).join(f"- {item}" for item in package["main_merge_disallowed_scope"])}

## Required validation before merge

```powershell
python -X utf8 -m src.main --help
python -X utf8 -m pytest -q
```

## Safety confirmation

- No CAD execution
- No ZWCAD COM SendCommand
- No XiCAD alias execution
- No Domain Rule Command Plan execution
- No original DWG mutation
- No final live runner implementation
- Local-only validation remains post-merge/manual

## Post-merge local-only validation

Use `docs/98_local_only_zwcad_xicad_validation_runbook.md`.
"""


def build_post_merge_local_validation_prompt(package: dict[str, Any]) -> str:
    steps = package.get("post_merge_local_validation") or []
    lines = [
        "너는 HS-CAD 로컬 Windows/ZWCAD 검증 에이전트다.",
        "",
        "이 작업은 main 병합 후 또는 main readiness 승인 후에만 수행한다.",
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
        "로컬 검증 순서:",
        "",
    ]
    for idx, step in enumerate(steps, start=1):
        lines.append(f"{idx}. {step.get('title')}")
        lines.append(f"   환경: {step.get('environment')}")
        lines.append(f"   명령 템플릿: {step.get('command')}")
        lines.append("   확인:")
        for check in step.get("required_confirmations", []):
            lines.append(f"   - {check}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def write_main_merge_decision_outputs(
    repo_root: str | Path = ".",
    post_pr53_workspace: str | Path = "outputs/post_pr53_main_merge_local_validation",
    *,
    out_dir: str | Path = "outputs/main_merge_readiness_decision",
) -> dict[str, Any]:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    package = build_main_merge_readiness_decision(repo_root=repo_root, post_pr53_workspace=post_pr53_workspace)

    decision_json = out / "MAIN_MERGE_READINESS_DECISION.json"
    decision_md = out / "MAIN_MERGE_READINESS_DECISION.md"
    pr_body = out / "MAIN_MERGE_PR_BODY_DRAFT.md"
    local_prompt = out / "POST_MERGE_LOCAL_VALIDATION_PROMPT.md"

    decision_json.write_text(json.dumps(package, ensure_ascii=False, indent=2), encoding="utf-8")
    decision_md.write_text(render_main_merge_decision_markdown(package), encoding="utf-8")
    pr_body.write_text(build_main_merge_pr_body(package), encoding="utf-8")
    local_prompt.write_text(build_post_merge_local_validation_prompt(package), encoding="utf-8")

    return {
        "status": package["status"],
        "out_dir": str(out),
        "decision_json": str(decision_json),
        "decision_md": str(decision_md),
        "main_merge_pr_body_draft": str(pr_body),
        "post_merge_local_validation_prompt": str(local_prompt),
        "safety": package["safety"],
    }
