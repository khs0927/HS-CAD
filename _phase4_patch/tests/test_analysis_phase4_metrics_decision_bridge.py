from __future__ import annotations

import json
from pathlib import Path

from src.analysis.phase4_metrics_decision_bridge import (
    build_phase4_bridge_report,
    write_phase4_bridge_outputs,
)


def make_phase3_report(path: Path, *, discovered: int = 3, missing: int = 2) -> None:
    payload = {
        "workspace": str(path.parent),
        "status": "partial",
        "discovered_count": discovered,
        "missing_count": missing,
        "json_loadable_count": discovered,
        "metrics": {
            "expected_artifact_count": discovered + missing,
            "discovered_artifact_count": discovered,
            "missing_artifact_count": missing,
            "json_loadable_artifact_count": discovered,
            "coverage_ratio": discovered / (discovered + missing),
        },
        "groups": {
            "text_roles": {"expected": 2, "discovered": 1, "missing": 1, "json_loadable": 1},
            "tables": {"expected": 4, "discovered": 0, "missing": 4, "json_loadable": 0},
        },
        "safety": {
            "source_mutation_allowed": False,
            "cad_execution_allowed": False,
            "derived_artifacts_only": True,
        },
    }
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_phase4_bridge_builds_review_only_decision_candidates(tmp_path: Path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    phase3 = workspace / "PHASE3_REAL_DATA_BINDING_REPORT.json"
    make_phase3_report(phase3)

    report = build_phase4_bridge_report(workspace)

    assert report.status == "partial"
    assert report.safety["decision_package_is_review_only"] is True
    assert report.safety["cad_execution_allowed"] is False
    assert any(item.decision_id == "phase4:decision-package-readiness" for item in report.decision_candidates)


def test_phase4_bridge_missing_phase3_report_is_warning(tmp_path: Path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    report = build_phase4_bridge_report(workspace)

    assert report.status == "warning"
    assert report.decision_candidates[0].status == "blocked"
    assert report.safety["sendcommand_allowed"] is False


def test_phase4_bridge_writes_outputs(tmp_path: Path):
    workspace = tmp_path / "workspace"
    out_dir = tmp_path / "out"
    workspace.mkdir()
    make_phase3_report(workspace / "PHASE3_REAL_DATA_BINDING_REPORT.json")

    result = write_phase4_bridge_outputs(workspace, out_dir=out_dir)

    assert Path(result["report_json"]).exists()
    assert Path(result["report_md"]).exists()
    assert Path(result["decision_bridge_package"]).exists()

    payload = json.loads(Path(result["decision_bridge_package"]).read_text(encoding="utf-8"))
    assert payload["safety"]["derived_artifacts_only"] is True
    assert payload["safety"]["xicad_alias_execution_allowed"] is False
