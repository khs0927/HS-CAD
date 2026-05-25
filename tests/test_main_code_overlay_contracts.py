from __future__ import annotations

from pathlib import Path

from hscad.cad.layer_schema import LAYER_SCHEMA
from hscad.fileizers.batch_fileizer import BatchFileizer
from hscad.safety.policy import SAFETY_FLAGS, assert_safe_defaults
from tests.fixtures.minimal_floorplan_factory import write_minimal_floorplan_dxf


def test_layer_schema_contains_required_layers():
    for layer in ["COL", "WAL1", "WAL2", "WAL3", "DOOR", "WIN", "CEN", "AI_LOWCONF", "QA_MARKUP"]:
        assert layer in LAYER_SCHEMA


def test_safety_flags_are_review_only():
    assert_safe_defaults()
    assert SAFETY_FLAGS["cad_execution_allowed_by_default"] is False
    assert SAFETY_FLAGS["zwcad_com_sendcommand_allowed"] is False
    assert SAFETY_FLAGS["xicad_alias_execution_allowed"] is False
    assert SAFETY_FLAGS["original_dwg_mutation_allowed"] is False


def test_dxf_fileizer_extracts_entities(tmp_path: Path):
    fixture = write_minimal_floorplan_dxf(tmp_path / "minimal_floorplan.dxf")
    drawing = BatchFileizer().fileize_one(fixture)
    assert drawing.source_format == "dxf"
    assert len(drawing.entities) >= 6
    assert any(e.layer == "WAL1" for e in drawing.entities)
    assert any(e.text == "ROOM 101" for e in drawing.entities)
