from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


EXPECTED_PHASE_FILES = [
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
]

CLI_IMPORT_PATCH_FILES = [
    "MAIN_IMPORT_PHASE3_PATCH.txt",
    "MAIN_IMPORT_PHASE4_PATCH.txt",
    "MAIN_IMPORT_PHASE5_PATCH.txt",
    "MAIN_IMPORT_PHASE6_PATCH.txt",
    "MAIN_IMPORT_PHASE7_9_PATCH.txt",
    "MAIN_IMPORT_PHASE10_11_PATCH.txt",
    "MAIN_IMPORT_PHASE12_PATCH.txt",
]

WORKER_MANIFEST_PATCH_FILES = [
    "config/worker_manifest.phase3.patch.json",
    "config/worker_manifest.phase4.patch.json",
    "config/worker_manifest.phase5.patch.json",
    "config/worker_manifest.phase6.patch.json",
    "config/worker_manifest.phase7_9.patch.json",
    "config/worker_manifest.phase10_11.patch.json",
    "config/worker_manifest.phase12.patch.json",
]


@dataclass(frozen=True)
class FileCheck:
    path: str
    exists: bool
    size_bytes: int = 0
    json_loadable: bool = False
    warning: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class FinalTodoReadinessReport:
    workspace: str
    repo_root: str
    generated_at: str
    status: str
    phase_artifacts: list[FileCheck]
    cli_patch_files: list[FileCheck]
    worker_manifest_patch_files: list[FileCheck]
    safety: dict[str, Any]
    remaining_todos: list[dict[str, Any]]
    recommended_pr_sequence: list[str]
    warnings: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "workspace": self.workspace,
            "repo_root": self.repo_root,
            "generated_at": self.generated_at,
            "status": self.status,
            "phase_artifacts": [item.to_dict() for item in self.phase_artifacts],
            "cli_patch_files": [item.to_dict() for item in self.cli_patch_files],
            "worker_manifest_patch_files": [item.to_dict() for item in self.worker_manifest_patch_files],
            "safety": self.safety,
            "remaining_todos": self.remaining_todos,
            "recommended_pr_sequence": self.recommended_pr_sequence,
            "warnings": self.warnings,
        }


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _json_loadable(path: Path) -> tuple[bool, str]:
    if path.suffix.lower() != ".json":
        return False, ""
    try:
        json.loads(path.read_text(encoding="utf-8"))
        return True, ""
    except Exception as exc:  # noqa: BLE001
        return False, str(exc)


def _check_file(path: Path) -> FileCheck:
    if not path.exists():
        return FileCheck(path=str(path), exists=False, warning="missing")
    json_ok, warning = _json_loadable(path)
    return FileCheck(
        path=str(path),
        exists=True,
        size_bytes=path.stat().st_size,
        json_loadable=json_ok,
        warning=f"json_warning: {warning}" if warning else "",
    )


def _safety() -> dict[str, Any]:
    return {
        "source_mutation_allowed": False,
        "original_dwg_mutation_allowed": False,
        "cad_execution_allowed_by_default": False,
        "zwcad_com_allowed_by_default": False,
        "sendcommand_allowed_by_default": False,
        "xicad_alias_execution_allowed_by_default": False,
        "live_execution_ready": False,
        "final_runner_implemented": False,
        "review_pipeline_ready_target": True,
    }


def build_final_todo_readiness_report(
    repo_root: str | Path = ".",
    workspace: str | Path = "outputs/webhard_batch_100",
) -> FinalTodoReadinessReport:
    repo = Path(repo_root)
    workspace_path = Path(workspace)
    warnings: list[str] = []

    phase_artifacts = [_check_file(workspace_path / name) for name in EXPECTED_PHASE_FILES]
    cli_patch_files = [_check_file(repo / name) for name in CLI_IMPORT_PATCH_FILES]
    worker_manifest_patch_files = [_check_file(repo / name) for name in WORKER_MANIFEST_PATCH_FILES]

    phase_existing = sum(1 for item in phase_artifacts if item.exists)
    cli_patch_existing = sum(1 for item in cli_patch_files if item.exists)
    worker_patch_existing = sum(1 for item in worker_manifest_patch_files if item.exists)

    if phase_existing < len(phase_artifacts):
        warnings.append("Not all Phase 3~12 artifacts exist in the selected workspace.")
    if cli_patch_existing < len(cli_patch_files):
        warnings.append("Some CLI import patch files are missing; they may not have been applied yet.")
    if worker_patch_existing < len(worker_manifest_patch_files):
        warnings.append("Some worker manifest patch files are missing; they may not have been applied yet.")

    status = "ready_for_final_review" if phase_existing == len(phase_artifacts) else "partial"

    remaining_todos = [
        {
            "id": "todo:pr-stack",
            "title": "Verify PR stack and branch order",
            "status": "required",
            "notes": "Ensure Phase 3,4,5,6,7-9,10-11,12 branches are pushed and PRs target the previous phase branch.",
        },
        {
            "id": "todo:cli-registration",
            "title": "Register Phase 3~12 CLI modules in src/main.py",
            "status": "pending",
            "notes": "Only after import-safety checks pass. Use MAIN_IMPORT_PHASE*.txt files.",
        },
        {
            "id": "todo:worker-manifest",
            "title": "Merge worker_manifest phase patch files",
            "status": "pending",
            "notes": "Merge config/worker_manifest.phase*.patch.json entries into config/worker_manifest.json in a separate PR.",
        },
        {
            "id": "todo:full-pytest",
            "title": "Run full pytest and src.main --help",
            "status": "required",
            "notes": "Required before any integration branch becomes main-ready.",
        },
        {
            "id": "todo:live-runner",
            "title": "Keep final live runner disabled",
            "status": "blocked_by_design",
            "notes": "Do not implement live SendCommand runner until manual safety review and copied-DWG validation are completed.",
        },
    ]

    recommended_pr_sequence = [
        "feat/analysis-phase3-real-data-binding",
        "feat/analysis-phase4-metrics-decision-bridge",
        "feat/analysis-phase5-domain-rule-decision-bridge",
        "feat/analysis-phase6-domain-rule-workflow-adapter",
        "feat/analysis-phase7-9-review-pipeline-bundle",
        "feat/analysis-phase10-11-domain-copy-validation",
        "feat/analysis-phase12-manual-live-execution-candidate",
        "reg/final-analysis-cli-registration",
        "reg/final-analysis-worker-manifest",
        "integration/final-review-pipeline-readiness",
    ]

    return FinalTodoReadinessReport(
        workspace=str(workspace_path),
        repo_root=str(repo),
        generated_at=_now(),
        status=status,
        phase_artifacts=phase_artifacts,
        cli_patch_files=cli_patch_files,
        worker_manifest_patch_files=worker_manifest_patch_files,
        safety=_safety(),
        remaining_todos=remaining_todos,
        recommended_pr_sequence=recommended_pr_sequence,
        warnings=warnings,
    )


def render_final_todo_markdown(report: FinalTodoReadinessReport) -> str:
    data = report.to_dict()
    lines = [
        "# HS-CAD Final TODO Integration Readiness Report",
        "",
        "## Summary",
        "",
        f"- Repo root: `{data['repo_root']}`",
        f"- Workspace: `{data['workspace']}`",
        f"- Status: `{data['status']}`",
        "",
        "## Phase Artifact Checks",
        "",
    ]

    for item in data["phase_artifacts"]:
        lines.append(f"- `{Path(item['path']).name}`: exists=`{item['exists']}`, json=`{item['json_loadable']}`")

    lines += ["", "## CLI Patch Files", ""]
    for item in data["cli_patch_files"]:
        lines.append(f"- `{Path(item['path']).name}`: exists=`{item['exists']}`")

    lines += ["", "## Worker Manifest Patch Files", ""]
    for item in data["worker_manifest_patch_files"]:
        lines.append(f"- `{Path(item['path']).name}`: exists=`{item['exists']}`, json=`{item['json_loadable']}`")

    lines += ["", "## Remaining TODO", ""]
    for todo in data["remaining_todos"]:
        lines.append(f"- `{todo['id']}` / {todo['status']}: {todo['title']} — {todo['notes']}")

    lines += ["", "## Recommended PR Sequence", ""]
    for idx, item in enumerate(data["recommended_pr_sequence"], start=1):
        lines.append(f"{idx}. `{item}`")

    lines += ["", "## Safety", ""]
    for key, value in data["safety"].items():
        lines.append(f"- `{key}`: `{value}`")

    lines += ["", "## Warnings", ""]
    if data["warnings"]:
        lines.extend(f"- {warning}" for warning in data["warnings"])
    else:
        lines.append("- None")

    return "\n".join(lines).rstrip() + "\n"


def write_final_todo_readiness_outputs(
    repo_root: str | Path = ".",
    workspace: str | Path = "outputs/webhard_batch_100",
    *,
    out_dir: str | Path = "outputs/final_todo_integration_readiness",
) -> dict[str, Any]:
    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    report = build_final_todo_readiness_report(repo_root=repo_root, workspace=workspace)
    payload = report.to_dict()

    json_path = out_path / "FINAL_TODO_INTEGRATION_READINESS.json"
    md_path = out_path / "FINAL_TODO_INTEGRATION_READINESS.md"
    pr_plan_path = out_path / "FINAL_PR_SEQUENCE_PLAN.json"

    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(render_final_todo_markdown(report), encoding="utf-8")
    pr_plan_path.write_text(
        json.dumps(
            {
                "status": report.status,
                "recommended_pr_sequence": report.recommended_pr_sequence,
                "remaining_todos": report.remaining_todos,
                "safety": report.safety,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    return {
        "status": report.status,
        "out_dir": str(out_path),
        "report_json": str(json_path),
        "report_md": str(md_path),
        "pr_sequence_plan": str(pr_plan_path),
        "warnings": report.warnings,
        "safety": report.safety,
    }
