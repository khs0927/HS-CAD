from __future__ import annotations

from pathlib import Path

from src.orchestrator.xicad_contracts import XiCADContractEvidence, write_evidence
from src.orchestrator.xicad_promotion_review import build_promotion_review_pack


def test_promotion_review_pack_does_not_modify_registry(tmp_path: Path):
    records = tmp_path / "records"
    records.mkdir()
    write_evidence(
        XiCADContractEvidence(
            alias="WAL",
            status="passed",
            manual_zwcad_version="ZWCAD 2026",
            xicad_root="C:/XICAD",
            observed_prompt_sequence=("start", "end"),
            accepted_argument_pattern=("point", "point"),
            output_observation="wall created",
            rollback_observation="undo ok",
            safety_observation="safe",
            no_save_confirmed=True,
            no_delete_confirmed=True,
            no_explode_confirmed=True,
        ),
        records / "WAL_record.json",
    )
    paths = build_promotion_review_pack(records, tmp_path / "review")
    assert Path(paths["json"]).exists()
    payload = Path(paths["json"]).read_text(encoding="utf-8")
    assert '"auto_modify_recipe_registry": false' in payload
    assert '"candidate_count": 1' in payload
