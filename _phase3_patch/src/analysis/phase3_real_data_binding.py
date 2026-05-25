from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PHASE1_ARTIFACT_CANDIDATES: dict[str, list[str]] = {
    "text_roles": ["TEXT_ROLE_INFERENCE.json", "TEXT_ROLE_INFERENCE.md"],
    "area_boundaries": ["AREA_BOUNDARY_INFERENCE.json", "REAL_GEOMETRY_POLYGONIZER.json"],
    "geometry_loops": ["GEOMETRY_LOOP_BUILDER.json", "GEOMETRY_LOOP_BUILDER.md"],
    "leaders": ["LEADER_GRAPH.json", "LEADER_NOTE_INFERENCE.json"],
    "dimensions": ["DIMENSION_GRAPH.json", "DIMENSION_TEXT_INFERENCE.json"],
    "tables": ["TABLE_GRID_DETECTOR.json", "TABLE_REGION_INFERENCE.json", "TABLE_CELL_EXTRACTOR.json"],
    "titleblocks": ["TITLEBLOCK_CLASSIFIER.json", "TITLEBLOCK_INFERENCE.json", "TITLEBLOCK_KEY_VALUES.json"],
    "sheet_profile": ["DRAWING_SHEET_CLASSIFIER.json", "DRAWING_SET_INDEX.json", "LAYER_PROFILE_SAMPLE.json"],
    "evidence_fusion": ["EVIDENCE_JOIN_FUSION.json", "VALIDATION_RULE_RESULTS.json"],
    "phase2_reports": ["ANALYSIS_EXPORT_MANIFEST.json", "ANALYSIS_STORAGE_MANIFEST.json", "ANALYSIS_REPORT_PACKAGE.json", "PIPELINE_EXECUTION_REPORT.json", "FINAL_APPLY_PLAN.json"],
}

@dataclass(frozen=True)
class ArtifactRecord:
    group: str
    name: str
    path: str
    exists: bool
    size_bytes: int = 0
    json_loadable: bool = False
    top_level_type: str = ""
    item_count: int = 0
    keys: list[str] = field(default_factory=list)
    warning: str = ""
    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

@dataclass(frozen=True)
class Phase3RealDataBindingReport:
    workspace: str
    generated_at: str
    status: str
    discovered_count: int
    missing_count: int
    json_loadable_count: int
    groups: dict[str, dict[str, Any]]
    records: list[ArtifactRecord]
    metrics: dict[str, Any]
    warnings: list[str]
    safety: dict[str, Any]
    def to_dict(self) -> dict[str, Any]:
        return {
            "workspace": self.workspace,
            "generated_at": self.generated_at,
            "status": self.status,
            "discovered_count": self.discovered_count,
            "missing_count": self.missing_count,
            "json_loadable_count": self.json_loadable_count,
            "groups": self.groups,
            "records": [r.to_dict() for r in self.records],
            "metrics": self.metrics,
            "warnings": self.warnings,
            "safety": self.safety,
        }

def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

def _read_json_if_possible(path: Path) -> tuple[bool, str, int, list[str], str]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        return False, "", 0, [], str(exc)
    top_type = type(data).__name__
    item_count = 0
    keys: list[str] = []
    if isinstance(data, dict):
        keys = sorted(str(k) for k in data.keys())[:50]
        item_count = len(data)
    elif isinstance(data, list):
        item_count = len(data)
        if data and isinstance(data[0], dict):
            keys = sorted(str(k) for k in data[0].keys())[:50]
    return True, top_type, item_count, keys, ""

def scan_phase1_artifacts(workspace: str | Path, *, candidates: dict[str, list[str]] | None = None) -> Phase3RealDataBindingReport:
    workspace_path = Path(workspace)
    candidates = candidates or PHASE1_ARTIFACT_CANDIDATES
    records: list[ArtifactRecord] = []
    warnings: list[str] = []
    groups: dict[str, dict[str, Any]] = {}
    for group, names in candidates.items():
        group_records: list[ArtifactRecord] = []
        for name in names:
            path = workspace_path / name
            if not path.exists():
                record = ArtifactRecord(group=group, name=name, path=str(path), exists=False, warning="artifact_missing")
                records.append(record); group_records.append(record); continue
            json_loadable = False; top_type = ""; item_count = 0; keys: list[str] = []; warning = ""
            if path.suffix.lower() == ".json":
                json_loadable, top_type, item_count, keys, err = _read_json_if_possible(path)
                if err: warning = f"json_parse_warning: {err}"
            record = ArtifactRecord(group=group, name=name, path=str(path), exists=True, size_bytes=path.stat().st_size, json_loadable=json_loadable, top_level_type=top_type, item_count=item_count, keys=keys, warning=warning)
            records.append(record); group_records.append(record)
        discovered = [r for r in group_records if r.exists]
        groups[group] = {"expected": len(group_records), "discovered": len(discovered), "missing": len(group_records)-len(discovered), "json_loadable": sum(1 for r in group_records if r.json_loadable), "artifacts": [r.to_dict() for r in group_records]}
    discovered_count = sum(1 for r in records if r.exists)
    missing_count = sum(1 for r in records if not r.exists)
    json_loadable_count = sum(1 for r in records if r.json_loadable)
    for group, summary in groups.items():
        if summary["discovered"] == 0:
            warnings.append(f"No artifacts discovered for group: {group}")
    metrics = {"expected_artifact_count": len(records), "discovered_artifact_count": discovered_count, "missing_artifact_count": missing_count, "json_loadable_artifact_count": json_loadable_count, "coverage_ratio": round(discovered_count / len(records), 4) if records else 0, "group_count": len(groups), "groups_with_any_artifact": sum(1 for item in groups.values() if item["discovered"] > 0)}
    status = "ok"
    if discovered_count == 0:
        status = "warning"; warnings.append("No phase1/phase2 artifacts were discovered in the workspace.")
    elif missing_count > 0:
        status = "partial"
    return Phase3RealDataBindingReport(workspace=str(workspace_path), generated_at=_utc_now_iso(), status=status, discovered_count=discovered_count, missing_count=missing_count, json_loadable_count=json_loadable_count, groups=groups, records=records, metrics=metrics, warnings=warnings, safety={"source_mutation_allowed": False, "cad_execution_allowed": False, "zwcad_com_allowed": False, "xicad_alias_execution_allowed": False, "derived_artifacts_only": True})

def render_phase3_markdown(report: Phase3RealDataBindingReport) -> str:
    data = report.to_dict()
    lines = ["# HS-CAD Phase 3 Real Data Binding Report", "", "## Summary", "", f"- Workspace: `{data['workspace']}`", f"- Status: `{data['status']}`", f"- Discovered artifacts: `{data['discovered_count']}`", f"- Missing artifacts: `{data['missing_count']}`", f"- JSON-loadable artifacts: `{data['json_loadable_count']}`", f"- Coverage ratio: `{data['metrics']['coverage_ratio']}`", "", "## Safety", ""]
    for key, value in data["safety"].items(): lines.append(f"- `{key}`: `{value}`")
    lines += ["", "## Group Coverage", ""]
    for group, summary in data["groups"].items(): lines.append(f"- `{group}`: discovered `{summary['discovered']}` / expected `{summary['expected']}`, json `{summary['json_loadable']}`")
    lines += ["", "## Warnings", ""]
    lines.extend([f"- {w}" for w in data["warnings"]] or ["- None"])
    lines += ["", "## Discovered Artifacts", ""]
    for record in data["records"]:
        if record["exists"]: lines.append(f"- `{record['name']}` | group=`{record['group']}` | size={record['size_bytes']} | json={record['json_loadable']}")
    return "\n".join(lines).rstrip() + "\n"

def write_phase3_real_data_binding_outputs(workspace: str | Path, *, out_dir: str | Path | None = None) -> dict[str, Any]:
    workspace_path = Path(workspace)
    out_path = Path(out_dir) if out_dir else workspace_path
    out_path.mkdir(parents=True, exist_ok=True)
    report = scan_phase1_artifacts(workspace_path)
    report_json = out_path / "PHASE3_REAL_DATA_BINDING_REPORT.json"
    report_md = out_path / "PHASE3_REAL_DATA_BINDING_REPORT.md"
    coverage_json = out_path / "PHASE3_ARTIFACT_COVERAGE.json"
    report_json.write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    report_md.write_text(render_phase3_markdown(report), encoding="utf-8")
    coverage_json.write_text(json.dumps({"workspace": str(workspace_path), "generated_at": report.generated_at, "status": report.status, "metrics": report.metrics, "groups": {g: {"expected": s["expected"], "discovered": s["discovered"], "missing": s["missing"], "json_loadable": s["json_loadable"]} for g, s in report.groups.items()}, "safety": report.safety}, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"status": report.status, "workspace": str(workspace_path), "out_dir": str(out_path), "report_json": str(report_json), "report_md": str(report_md), "coverage_json": str(coverage_json), "metrics": report.metrics, "warnings": report.warnings}
