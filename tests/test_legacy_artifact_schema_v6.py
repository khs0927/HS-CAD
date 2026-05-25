from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from hscad.connectors.artifact_schema import extract_artifact_records, summarize_artifact_schema
from hscad.connectors.legacy_artifact_adapter import LegacyArtifactAdapter
from tests.fixtures.legacy_schema_artifact_factory import write_schema_variant_legacy_artifacts


def test_schema_aware_record_extraction_from_nested_payload() -> None:
    payload = {"data": {"layers": {"WAL1": {"semantic_role": "wall", "confidence": 0.91}}}}
    records = extract_artifact_records(payload, "layer_semantics", preferred_keys=("layers",))
    assert len(records) == 1
    assert records[0]["name"] == "WAL1"
    assert records[0]["semantic_role"] == "wall"
    assert records[0]["_stable_id"] == "WAL1"

    summary = summarize_artifact_schema(payload, "layer_semantics")
    assert summary.record_count == 1
    assert summary.record_path.endswith("layers")
    assert "semantic_role" in summary.record_keys


def test_legacy_artifact_adapter_accepts_schema_variant_outputs(tmp_path: Path) -> None:
    legacy_dir = write_schema_variant_legacy_artifacts(tmp_path / "legacy")
    result = LegacyArtifactAdapter(max_detail_records=20).load(legacy_dir)

    assert result.warnings == []
    assert len(result.artifacts) == 5
    assert result.by_kind["layer_semantic_role"] == 3
    assert result.by_kind["legacy_text_role"] == 2
    assert result.by_kind["legacy_area_element"] == 2
    assert result.by_kind["legacy_conflict"] == 1
    assert result.by_kind["domain_rule_result"] == 2

    artifact_records = [artifact.to_record() for artifact in result.artifacts]
    assert all("schema" in artifact for artifact in artifact_records)
    assert any(artifact["schema"]["record_count"] >= 2 for artifact in artifact_records)


def test_inspect_legacy_artifact_schema_script_outputs_json(tmp_path: Path) -> None:
    legacy_dir = write_schema_variant_legacy_artifacts(tmp_path / "legacy")
    report_path = tmp_path / "schema_report.json"

    subprocess.run(
        [
            sys.executable,
            "-X",
            "utf8",
            "scripts/inspect_legacy_artifact_schema.py",
            "--legacy-dir",
            str(legacy_dir),
            "--out",
            str(report_path),
        ],
        check=True,
    )

    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["artifact_count"] == 5
    assert report["total_record_count"] >= 10
    assert "LAYER_SEMANTICS.json" in report["artifacts"]
