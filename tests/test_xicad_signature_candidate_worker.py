from __future__ import annotations

from pathlib import Path

from src.reports.json_exporter import export_json
from src.workers.xicad_signature_candidate_worker import run_xicad_signature_candidate_worker


def test_signature_candidate_worker_writes_delta_candidate_and_report(tmp_path: Path):
    before = tmp_path / "before.json"
    after = tmp_path / "after.json"
    out_dir = tmp_path / "signature"

    export_json({"objects": []}, before)
    export_json(
        {
            "objects": [
                {
                    "handle": "10",
                    "layer": "WAL",
                    "entity_type": "LINE",
                    "start": [0, 0],
                    "end": [3000, 0],
                },
                {
                    "handle": "11",
                    "layer": "WAL",
                    "entity_type": "LINE",
                    "start": [0, 180],
                    "end": [3000, 180],
                },
            ]
        },
        after,
    )

    result = run_xicad_signature_candidate_worker(
        alias="WAL",
        before_snapshot_json=before,
        after_snapshot_json=after,
        out_dir=out_dir,
    )

    assert result["status"] == "candidate"
    assert result["requires_human_review"] is True
    assert result["geometry_pattern_count"] == 1
    assert result["added_count"] == 2
    assert Path(result["entity_delta"]).exists()
    assert Path(result["signature_candidate"]).exists()
    assert Path(result["report"]).exists()
