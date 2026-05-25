from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


EXPECTED_PHASE_ARTIFACTS = [
    "PHASE3_REAL_DATA_BINDING_REPORT.json",
    "PHASE4_DECISION_BRIDGE_PACKAGE.json",
    "PHASE5_DOMAIN_RULE_INPUT_PACKAGE.json",
    "DOMAIN_RULE_DECISION_INPUT_FROM_PHASE6.json",
    "PHASE7_DOMAIN_DECISION_PACKAGE.json",
    "PHASE8_REVIEW_GATE_CHAIN.json",
]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safety() -> dict[str, Any]:
    return {
        "source_mutation_allowed": False,
        "cad_execution_allowed": False,
        "zwcad_com_allowed": False,
        "sendcommand_allowed": False,
        "xicad_alias_execution_allowed": False,
        "execution_allowed": False,
        "ready_for_live_execution": False,
        "ready_for_review_only_pipeline": True,
    }


def build_phase9_readiness_summary(workspace: str | Path) -> dict[str, Any]:
    workspace_path = Path(workspace)
    artifacts: list[dict[str, Any]] = []
    for name in EXPECTED_PHASE_ARTIFACTS:
        path = workspace_path / name
        record = {
            "name": name,
            "path": str(path),
            "exists": path.exists(),
            "size_bytes": path.stat().st_size if path.exists() else 0,
            "json_loadable": False,
            "status": "missing",
        }
        if path.exists():
            try:
                json.loads(path.read_text(encoding="utf-8"))
                record["json_loadable"] = True
                record["status"] = "ok"
            except Exception as exc:  # noqa: BLE001
                record["status"] = f"json_warning: {exc}"
        artifacts.append(record)

    existing_count = sum(1 for item in artifacts if item["exists"])
    json_count = sum(1 for item in artifacts if item["json_loadable"])
    missing = [item["name"] for item in artifacts if not item["exists"]]

    status = "ready_for_review_pipeline" if existing_count == len(artifacts) and json_count == len(artifacts) else "partial"
    if existing_count == 0:
        status = "blocked"

    return {
        "task": "phase9_pipeline_readiness_summary",
        "workspace": str(workspace_path),
        "generated_at": _now(),
        "status": status,
        "artifact_count": len(artifacts),
        "existing_count": existing_count,
        "json_loadable_count": json_count,
        "missing_artifacts": missing,
        "artifacts": artifacts,
        "recommended_next_steps": _next_steps(status, missing),
        "safety": _safety(),
    }


def _next_steps(status: str, missing: list[str]) -> list[str]:
    if status == "ready_for_review_pipeline":
        return [
            "Run review-only Domain Rule Decision Workflow adapter.",
            "Compare decision/review-gate outputs against sample drawings.",
            "Do not enable live execution yet.",
        ]
    if status == "blocked":
        return [
            "Run Phase 3 real-data binding first.",
            "Then run Phase 4, Phase 5, Phase 6, Phase 7, and Phase 8 in order.",
        ]
    return [
        f"Generate missing artifact: {name}" for name in missing
    ] + ["Keep execution disabled."]


def render_phase9_markdown(summary: dict[str, Any]) -> str:
    lines = [
        "# HS-CAD Phase 9 Pipeline Readiness Summary",
        "",
        f"- Workspace: `{summary['workspace']}`",
        f"- Status: `{summary['status']}`",
        f"- Existing artifacts: `{summary['existing_count']}` / `{summary['artifact_count']}`",
        f"- JSON-loadable artifacts: `{summary['json_loadable_count']}`",
        "",
        "## Artifacts",
        "",
    ]
    for item in summary["artifacts"]:
        lines.append(f"- `{item['name']}` | exists=`{item['exists']}` | json=`{item['json_loadable']}` | status=`{item['status']}`")

    lines += ["", "## Recommended Next Steps", ""]
    lines.extend(f"- {step}" for step in summary["recommended_next_steps"])

    lines += ["", "## Safety", ""]
    for key, value in summary["safety"].items():
        lines.append(f"- `{key}`: `{value}`")
    return "\n".join(lines).rstrip() + "\n"


def write_phase9_outputs(
    workspace: str | Path,
    *,
    out_dir: str | Path | None = None,
) -> dict[str, Any]:
    workspace_path = Path(workspace)
    out_path = Path(out_dir) if out_dir else workspace_path
    out_path.mkdir(parents=True, exist_ok=True)

    summary = build_phase9_readiness_summary(workspace_path)
    json_path = out_path / "PHASE9_PIPELINE_READINESS_SUMMARY.json"
    md_path = out_path / "PHASE9_PIPELINE_READINESS_SUMMARY.md"

    json_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(render_phase9_markdown(summary), encoding="utf-8")

    return {
        "status": summary["status"],
        "workspace": str(workspace_path),
        "out_dir": str(out_path),
        "summary_json": str(json_path),
        "summary_md": str(md_path),
        "missing_artifacts": summary["missing_artifacts"],
        "safety": summary["safety"],
    }
