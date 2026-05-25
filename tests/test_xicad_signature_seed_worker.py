from __future__ import annotations

from pathlib import Path

from src.workers.xicad_signature_seed_worker import run_xicad_signature_seed_worker


def test_signature_seed_worker_handles_missing_xicad_root(tmp_path: Path):
    result = run_xicad_signature_seed_worker(
        xicad_root=str(tmp_path / "missing"),
        out_dir=tmp_path / "seeds",
    )

    assert result["loaded"] is False
    assert result["seed_count"] == 0
    assert Path(result["seeds_json"]).exists()
    assert Path(result["report"]).exists()
