from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PR_STACK = [
    {
        "pr": "#55",
        "url": "https://github.com/khs0927/HS-CAD/pull/55",
        "branch": "integration/main-merge-readiness-decision",
        "purpose": "Main merge readiness decision package",
        "reported": [
            "200 passed, 16 skipped",
            "ruff E9,F63,F7,F82,F821 passed",
            "src.main --help passed",
            "hscad-main-merge-readiness-decision passed",
            "decision status: ready_for_human_main_merge_review",
        ],
    },
    {
        "pr": "#56",
        "url": "https://github.com/khs0927/HS-CAD/pull/56",
        "branch": "integration/main-ready-review-only-pipeline",
        "purpose": "Main-based review-only integration validation",
        "reported": [
            "206 passed, 16 skipped",
            "compileall passed",
            "CLI smoke passed",
            "main-ready judgment: yes",
            "no CAD execution",
        ],
    },
    {
        "pr": "#57",
        "url": "local/operator-review-stage",
        "branch": "integration/main-merge-operator-review",
        "purpose": "Main merge operator review package",
        "reported": [
            "operator review package prepared",
            "main merge not executed",
            "post-merge local validation prompt prepared",
            "final live runner still blocked",
        ],
    },
    {
        "pr": "#58",
        "url": "https://github.com/khs0927/HS-CAD/pull/58",
        "branch": "planning/post-main-local-validation-live-runner-safety",
        "purpose": "Post-main local validation and final live runner safety planning",
        "reported": [
            "218 passed, 16 skipped",
            "compileall passed",
            "CLI smoke passed",
            "post-main local validation manual-only",
            "final live runner requires separate safety spec PR",
        ],
    },
    {
        "pr": "#59",
        "url": "https://github.com/khs0927/HS-CAD/pull/59",
        "branch": "human/main-merge-review-gate",
        "purpose": "Human main merge review gate",
        "reported": [
            "tests/test_human_main_merge_review_gate.py: 3 passed",
            "227 passed, 16 skipped",
            "compileall passed",
            "CLI smoke passed",
            "human review ready yes",
            "auto merge false",
            "final live runner not implemented",
        ],
    },
]


COMBINED_ALLOWED_SCOPE = [
    "review-only analysis pipeline",
    "plan-only Domain Rule bridge",
    "main-readiness decision package",
    "main-ready review-only validation",
    "main merge operator review package",
    "post-main local validation planning",
    "final live runner safety requirements seed",
    "human main merge review gate",
    "manual-only copied-DWG validation runbooks",
]


COMBINED_DISALLOWED_SCOPE = [
    "actual main merge by automation",
    "direct push to main",
    "ZWCAD COM SendCommand execution",
    "XiCAD alias execution",
    "Domain Rule Command Plan execution",
    "copied-DWG live validation in this PR",
    "original DWG mutation",
    "final live runner implementation",
    "automatic operator approval",
    "outputs/DWG/DXF/cache committed",
]


PRE_MERGE_VALIDATION_COMMANDS = [
    "git fetch origin",
    "git switch human/main-merge-review-gate",
    "git pull --ff-only",
    "python -X utf8 -m compileall -q src tests",
    "python -X utf8 -m pytest -q",
    "python -X utf8 -m src.main --help",
    "python -X utf8 -m src.main hscad-human-main-merge-review-gate --repo-root . --post-main-safety-workspace outputs\\post_main_local_validation_live_runner_safety --out-dir outputs\\human_main_merge_review_gate",
]


POST_MERGE_MANUAL_COMMANDS = [
    {
        "id": "post-merge-01-copy-scan",
        "title": "Copied DWG scan validation",
        "command": 'python -X utf8 -m src.main zwcad-copy-scan-validate --original-dwg "C:/cad/test/original.dwg" --working-copy-dwg "C:/cad/test_work/copy.dwg" --out-dir outputs/zwcad_copy_validation_live',
        "manual_only": True,
        "requires": ["Windows", "ZWCAD", "copied DWG"],
    },
    {
        "id": "post-merge-02-copy-saveas",
        "title": "Copied DWG SaveAs validation",
        "command": 'python -X utf8 -m src.main zwcad-copy-saveas-validate --original-dwg "C:/cad/test/original.dwg" --working-copy-dwg "C:/cad/test_work/copy.dwg" --save-as-target "C:/cad/test_work/result.dwg" --out-dir outputs/zwcad_copy_saveas_validation_live --overwrite-copy',
        "manual_only": True,
        "requires": ["Windows", "ZWCAD", "copied DWG", "distinct SaveAs target"],
    },
    {
        "id": "post-merge-03-xicad-policy",
        "title": "C:/xicad allowlist policy validation",
        "command": 'python -X utf8 -m src.main xicad-policy-candidates --xicad-root C:/xicad --out-dir outputs/xicad_policy_candidates_verify',
        "manual_only": True,
        "requires": ["Windows", "C:/xicad"],
    },
    {
        "id": "post-merge-04-phase12-guard",
        "title": "Phase 12 candidate guard only",
        "command": "python -X utf8 -m src.main hscad-analysis-phase12-manual-live-candidate --workspace outputs/phase10_11_domain_copy_verify --alias WAL --manual-live-flag --operator-approved --out-dir outputs/phase12_manual_live_candidate_verify",
        "manual_only": True,
        "requires": ["copied DWG evidence", "allowlist evidence", "operator review"],
    },
]


@dataclass(frozen=True)
class ReviewGate:
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
        "this_package_merges_main": False,
        "main_direct_push_allowed": False,
        "auto_merge_allowed": False,
        "cad_execution_allowed": False,
        "zwcad_com_sendcommand_allowed": False,
        "xicad_alias_execution_allowed": False,
        "domain_rule_command_execution_allowed": False,
        "copied_dwg_live_validation_allowed_in_this_step": False,
        "original_dwg_mutation_allowed": False,
        "final_live_runner_implemented": False,
        "final_live_runner_allowed": False,
        "human_review_required": True,
        "post_merge_local_validation_manual_only": True,
    }


def build_pr55_59_combined_review(repo_root: str | Path = ".") -> dict[str, Any]:
    repo = Path(repo_root)

    gates = [
        ReviewGate(
            id="gate:pr-stack-context",
            title="PR #55~#59 stack context preserved",
            status="ready_for_human_review",
            evidence=[f"{item['pr']} {item['branch']} {item['url']}" for item in PR_STACK],
            next_action="Human reviewer must inspect PR diffs before merge.",
        ),
        ReviewGate(
            id="gate:scope-limited",
            title="Merge scope remains review-only / plan-only / safety-guard",
            status="ready_for_human_review",
            evidence=COMBINED_ALLOWED_SCOPE,
            blocked_reasons=[],
            next_action="Reject if any disallowed live execution behavior is present.",
        ),
        ReviewGate(
            id="gate:live-runner-blocked",
            title="Final live runner remains blocked",
            status="ok",
            evidence=["final_live_runner_implemented=false", "implementation_requires_separate_pr=true"],
            next_action="Do not implement live runner in PR #55~#59 merge.",
        ),
        ReviewGate(
            id="gate:post-merge-manual-only",
            title="Post-merge local validation remains manual-only",
            status="ok",
            evidence=[item["id"] for item in POST_MERGE_MANUAL_COMMANDS],
            next_action="Run only after human main merge decision and Windows/ZWCAD readiness.",
        ),
    ]

    return {
        "task": "pr55_59_combined_review",
        "generated_at": _now(),
        "repo_root": str(repo),
        "status": "ready_for_human_main_merge_review",
        "pr_stack": PR_STACK,
        "gates": [gate.to_dict() for gate in gates],
        "allowed_scope": COMBINED_ALLOWED_SCOPE,
        "disallowed_scope": COMBINED_DISALLOWED_SCOPE,
        "pre_merge_validation_commands": PRE_MERGE_VALIDATION_COMMANDS,
        "post_merge_manual_commands": POST_MERGE_MANUAL_COMMANDS,
        "decision": {
            "can_human_review_pr55_59_together": True,
            "can_auto_merge": False,
            "can_start_final_live_runner": False,
            "main_merge_requires_human_decision": True,
        },
        "safety": _safety(),
    }


def render_markdown(package: dict[str, Any]) -> str:
    lines = [
        "# HS-CAD PR #55~#59 Combined Review Package",
        "",
        f"- Status: `{package['status']}`",
        f"- Can auto merge: `{package['decision']['can_auto_merge']}`",
        f"- Can start final live runner: `{package['decision']['can_start_final_live_runner']}`",
        "",
        "## PR Stack",
        "",
    ]

    for item in package["pr_stack"]:
        lines.append(f"### {item['pr']} — {item['branch']}")
        lines.append(f"- URL: {item['url']}")
        lines.append(f"- Purpose: {item['purpose']}")
        lines.append("- Reported:")
        for report in item["reported"]:
            lines.append(f"  - {report}")
        lines.append("")

    lines += ["## Gates", ""]
    for gate in package["gates"]:
        lines.append(f"### {gate['id']}")
        lines.append(f"- Title: {gate['title']}")
        lines.append(f"- Status: `{gate['status']}`")
        lines.append(f"- Next action: {gate['next_action']}")
        lines.append("")

    lines += ["## Allowed Scope", ""]
    lines.extend(f"- {item}" for item in package["allowed_scope"])

    lines += ["", "## Disallowed Scope", ""]
    lines.extend(f"- {item}" for item in package["disallowed_scope"])

    lines += ["", "## Pre-merge Validation Commands", ""]
    for cmd in package["pre_merge_validation_commands"]:
        lines.append("```powershell")
        lines.append(cmd)
        lines.append("```")

    lines += ["", "## Post-merge Manual Commands", ""]
    for item in package["post_merge_manual_commands"]:
        lines.append(f"### {item['id']} — {item['title']}")
        lines.append("```powershell")
        lines.append(item["command"])
        lines.append("```")
        lines.append(f"- Manual only: `{item['manual_only']}`")
        lines.append(f"- Requires: {', '.join(item['requires'])}")
        lines.append("")

    lines += ["## Safety", ""]
    for key, value in package["safety"].items():
        lines.append(f"- `{key}`: `{value}`")

    return "\n".join(lines).rstrip() + "\n"


def build_operator_prompt(package: dict[str, Any]) -> str:
    return f"""너는 HS-CAD PR #55~#59 통합 검토 오퍼레이터다.

목표:
PR #55~#59를 한 번에 검토하고, main 병합 여부를 인간 검토자가 판단할 수 있도록 정리한다.

중요:
이 작업은 자동 main merge가 아니다.
main에 직접 push하지 않는다.
CAD/ZWCAD/XiCAD/SendCommand를 실행하지 않는다.
final live runner를 구현하지 않는다.

검토 대상:
{chr(10).join(f"- {item['pr']} {item['branch']} {item['url']}" for item in package['pr_stack'])}

허용 범위:
{chr(10).join(f"- {item}" for item in package['allowed_scope'])}

금지 범위:
{chr(10).join(f"- {item}" for item in package['disallowed_scope'])}

검증 명령:
{chr(10).join(f"- {cmd}" for cmd in package['pre_merge_validation_commands'])}

판정:
- human review 가능: {package['decision']['can_human_review_pr55_59_together']}
- auto merge 가능: {package['decision']['can_auto_merge']}
- final live runner 시작 가능: {package['decision']['can_start_final_live_runner']}
"""


def write_outputs(
    repo_root: str | Path = ".",
    *,
    out_dir: str | Path = "outputs/pr55_59_combined_review",
) -> dict[str, Any]:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    package = build_pr55_59_combined_review(repo_root=repo_root)

    package_json = out / "PR55_59_COMBINED_REVIEW_PACKAGE.json"
    package_md = out / "PR55_59_COMBINED_REVIEW_PACKAGE.md"
    operator_prompt = out / "PR55_59_OPERATOR_REVIEW_PROMPT.md"
    post_merge_json = out / "PR55_59_POST_MERGE_MANUAL_COMMANDS.json"

    package_json.write_text(json.dumps(package, ensure_ascii=False, indent=2), encoding="utf-8")
    package_md.write_text(render_markdown(package), encoding="utf-8")
    operator_prompt.write_text(build_operator_prompt(package), encoding="utf-8")
    post_merge_json.write_text(json.dumps(POST_MERGE_MANUAL_COMMANDS, ensure_ascii=False, indent=2), encoding="utf-8")

    return {
        "status": package["status"],
        "out_dir": str(out),
        "package_json": str(package_json),
        "package_md": str(package_md),
        "operator_prompt": str(operator_prompt),
        "post_merge_json": str(post_merge_json),
        "safety": package["safety"],
    }
