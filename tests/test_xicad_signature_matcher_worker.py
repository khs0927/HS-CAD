from __future__ import annotations

import json
from pathlib import Path

from src.workers.xicad_signature_matcher_worker import run_signature_matcher_worker


def test_signature_matcher_worker_writes_json_and_report(tmp_path: Path):
    snapshot_json = tmp_path / "snapshot.json"
    signatures_json = tmp_path / "signatures.json"
    out_dir = tmp_path / "matches"

    snapshot_json.write_text(
        json.dumps(
            {
                "objects": [
                    {"handle": "10", "layer": "C", "entity_type": "LINE", "start": [0, 0], "end": [1000, 0]},
                    {"handle": "11", "layer": "C", "entity_type": "LINE", "start": [0, 150], "end": [1000, 150]},
                ]
            }
        ),
        encoding="utf-8",
    )
    signatures_json.write_text(
        json.dumps(
            {
                "verified_signatures": [
                    {
                        "alias": "WAL",
                        "status": "verified",
                        "evidence": {
                            "matched_layers": ["C"],
                            "matched_types": ["LINE"],
                        },
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    result = run_signature_matcher_worker(
        snapshot_json=snapshot_json,
        signatures_json=signatures_json,
        out_dir=out_dir,
    )

    assert result["match_count"] == 1
    assert Path(result["matches_json"]).exists()
    assert Path(result["report"]).exists()
