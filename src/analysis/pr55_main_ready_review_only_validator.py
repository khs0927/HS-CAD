from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PR55_CONTEXT = {
    "branch": "integration/main-merge-readiness-decision",
    "pr_url": "https://github.com/khs0927/HS-CAD/pull/55",
    "status": "OPEN non-draft",
    "decision_status": "ready_for_human_main_merge_review",
    "reported_validation": {
        "pytest": "200 passed, 16 skipped",
        "ruff": "E9,F63,F7,F82,F821 all passed",
        "compileall": "passed",
        "src_main_help": "passed",
        "decision_cli": "hscad-main-merge-readiness-decision passed",
    },
    "latest_commits": [
        "613aa4b feat: add main merge readiness decision package",
        "6954104 fix: ruff F821 cleanup + extend ZWCADCOMAdapter API",
        "997b2b0 docs: add main merge readiness decision work report",
    ],
}


EXPECTED_REPORTS = [
    "docs/101_main_merge_readiness_decision_workreport.md",
    "docs/100_main_merge_readiness_decision_report.md",
    "docs/99_main_merge_readiness_decision_prompt.md",
    "docs/98_local_only_zwcad_xicad_validation_runbook.md",
    "docs/97_post_pr53_main_merge_local_validation_report.md",
    "docs/95_main_readiness_local_validation_report.md",
    "docs/93_final_review_pipeline_readiness_report.md",
    "docs/92_final_analysis_worker_manifest_registration_report.md",
    "docs/91_final_analysis_cli_registration_report.md",
    "docs/90_final_live_runner_deferred_safety_policy.md",
]

EXPECTED_COMMANDS = [
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
    "hscad-main-merge-readiness-decision",
]


@dataclass(frozen=True)
class ValidationGate:
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


def _safety() -> dict[str, Any]:
    return {
        "main_direct_push_allowed": False,
        "actual_main_merge_performed": False,
        "source_mutation_allowed": False,
        "original_dwg_mutation_allowed": False,
        "cad_execution_allowed": False,
        "zwcad_com_sendcommand_allowed": False,
        "xicad_alias_execution_allowed": False,
        "domain_rule_command_execution_allowed": False,
        "copied_dwg_live_validation_allowed": False,
        "final_live_runner_implemented": False,
        "final_live_runner_allowed": False,
        "review_only_pipeline_only": True,
    }


def build_pr55_main_ready_validation_report(
    repo_root: str | Path = ".",
    out_workspace: str | Path = "outputs/pr55_main_ready_review_only_validation",
) -> dict[str, Any]:
    repo = Path(repo_root)
    workspace = Path(out_workspace)
    gates: list[ValidationGate] = []

    missing_reports = [path for path in EXPECTED_REPORTS if not (repo / path).exists()]
    gates.append(
        ValidationGate(
            id="gate:expected-reports",
            title="Expected readiness/report docs exist",
            status="ok" if not missing_reports else "partial",
            evidence=[path for path in EXPECTED_REPORTS if (repo / path).exists()],
            blocked_reasons=[f"missing:{path}" for path in missing_reports],
            next_action="Missing older reports may be acceptable if PR stack intentionally excludes them; document before main merge.",
        )
    )

    main_py = repo / "src" / "main.py"
    command_evidence: list[str] = []
    missing_command_hints: list[str] = []
    if main_py.exists():
        text = main_py.read_text(encoding="utf-8", errors="ignore")
        for cmd in EXPECTED_COMMANDS:
            if cmd in text:
                command_evidence.append(cmd)
            else:
                missing_command_hints.append(cmd)
    else:
        missing_command_hints = EXPECTED_COMMANDS[:]

    gates.append(
        ValidationGate(
            id="gate:command-registration-hints",
            title="Review-only command registration hints",
            status="ok" if main_py.exists() else "blocked",
            evidence=command_evidence,
            blocked_reasons=["missing:src/main.py"] if not main_py.exists() else [],
            next_action="Run `python -X utf8 -m src.main --help` to confirm actual command registration.",
        )
    )

    forbidden_paths = []
    for pattern in ["outputs", "scratch", "_main_merge_decision_patch", "_post_pr53_patch", "_main_readiness_patch"]:
        path = repo / pattern
        if path.exists():
            forbidden_paths.append(str(path))

    gates.append(
        ValidationGate(
            id="gate:workspace-pollution-reminder",
            title="Generated output/temp directories are not committed",
            status="review_required",
            evidence=forbidden_paths,
            next_action="Use `git status --short` and confirm outputs/scratch/patch directories are untracked or ignored.",
        )
    )

    status = "ready_for_validation"
    if any(gate.status == "blocked" for gate in gates):
        status = "blocked"

    return {
        "task": "pr55_main_ready_review_only_validation",
        "generated_at": _now(),
        "repo_root": str(repo),
        "out_workspace": str(workspace),
        "status": status,
        "pr55_context": PR55_CONTEXT,
        "gates": [gate.to_dict() for gate in gates],
        "required_validation_commands": [
            "git fetch origin",
            "git switch integration/main-ready-review-only-pipeline",
            "python -X utf8 -m compileall -q src tests",
            "python -X utf8 -m ruff check src tests --select E9,F63,F7,F82,F821",
            "python -X utf8 -m pytest -q",
            "python -X utf8 -m src.main --help",
            "python -X utf8 -m src.main hscad-main-merge-readiness-decision --out-dir outputs/pr55_main_ready_review_only_validation",
        ],
        "expected_results": {
            "pytest": "200 passed, 16 skipped or better",
            "ruff": "All checks passed",
            "decision_status": "ready_for_human_main_merge_review",
        },
        "allowed_scope": [
            "review-only analysis pipeline",
            "plan-only Domain Rule bridge",
            "copied-DWG validation planning",
            "manual live candidate guard",
            "safety policy docs",
            "main-readiness decision artifacts",
        ],
        "disallowed_scope": [
            "actual main merge in this validation branch",
            "final live runner",
            "ZWCAD COM SendCommand execution",
            "XiCAD alias execution",
            "Domain Rule Command Plan execution",
            "copied-DWG live validation",
            "original DWG mutation",
            "automatic operator approval",
        ],
        "post_validation_next_steps": [
            "If validation is green, ask a human reviewer whether to merge review-only/plan-only/safety-guard scope to main.",
            "Keep local-only ZWCAD/XiCAD validation as manual post-merge work.",
            "Do not implement final live runner until separate safety-spec PR is approved.",
        ],
        "safety": _safety(),
    }


def render_pr55_validation_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# HS-CAD PR55 Main-ready Review-only Integration Validation",
        "",
        "## Summary",
        "",
        f"- PR #55: {report['pr55_context']['pr_url']}",
        f"- Source branch: `{report['pr55_context']['branch']}`",
        f"- Status: `{report['status']}`",
        f"- Decision status: `{report['pr55_context']['decision_status']}`",
        "",
        "## Reported PR #55 Validation",
        "",
    ]
    for key, value in report["pr55_context"]["reported_validation"].items():
        lines.append(f"- `{key}`: {value}")

    lines += ["", "## Gates", ""]
    for gate in report["gates"]:
        lines.append(f"### {gate['id']}")
        lines.append("")
        lines.append(f"- Title: {gate['title']}")
        lines.append(f"- Status: `{gate['status']}`")
        if gate["blocked_reasons"]:
            lines.append(f"- Blocked reasons: {', '.join(gate['blocked_reasons'])}")
        lines.append(f"- Next action: {gate['next_action']}")
        lines.append("")

    lines += ["## Required Validation Commands", ""]
    for cmd in report["required_validation_commands"]:
        lines.append("```powershell")
        lines.append(cmd)
        lines.append("```")

    lines += ["", "## Allowed Scope", ""]
    lines.extend(f"- {item}" for item in report["allowed_scope"])

    lines += ["", "## Disallowed Scope", ""]
    lines.extend(f"- {item}" for item in report["disallowed_scope"])

    lines += ["", "## Safety", ""]
    for key, value in report["safety"].items():
        lines.append(f"- `{key}`: `{value}`")

    return "\n".join(lines).rstrip() + "\n"


def write_pr55_validation_outputs(
    repo_root: str | Path = ".",
    *,
    out_dir: str | Path = "outputs/pr55_main_ready_review_only_validation",
) -> dict[str, Any]:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    report = build_pr55_main_ready_validation_report(repo_root=repo_root, out_workspace=out)

    json_path = out / "PR55_MAIN_READY_REVIEW_ONLY_VALIDATION.json"
    md_path = out / "PR55_MAIN_READY_REVIEW_ONLY_VALIDATION.md"
    checklist_path = out / "PR55_MAIN_READY_CHECKLIST.json"

    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(render_pr55_validation_markdown(report), encoding="utf-8")
    checklist_path.write_text(
        json.dumps(
            {
                "required_validation_commands": report["required_validation_commands"],
                "expected_results": report["expected_results"],
                "post_validation_next_steps": report["post_validation_next_steps"],
                "safety": report["safety"],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    return {
        "status": report["status"],
        "out_dir": str(out),
        "report_json": str(json_path),
        "report_md": str(md_path),
        "checklist_json": str(checklist_path),
        "safety": report["safety"],
    }
