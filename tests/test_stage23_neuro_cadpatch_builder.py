from pathlib import Path

from src.hs_style_context.builder import build_style_context
from src.neuro_seq_cad_bridge.cadpatch_builder import build_preview_insert_plan


def test_preview_plan_wallsolid_priority(tmp_path: Path):
    wallsolid = tmp_path / "wallsolid.dxf"
    centerline = tmp_path / "centerline.dxf"
    wallsolid.write_text("0\nEOF\n", encoding="utf-8")
    centerline.write_text("0\nEOF\n", encoding="utf-8")

    context = build_style_context(
        zium_sheet_area={"representative_usable_area": [10, 20, 100, 200]}
    )
    styled = {"entities": [{"original_entity": {"entity_type": "wall"}, "needs_review": False}]}

    plan = build_preview_insert_plan(styled, str(centerline), str(wallsolid), context)

    assert plan["source_dxf"] == str(wallsolid)
    assert plan["save"] is False
    assert plan["undo_mark_required"] is True
    assert plan["base_point"] == [10.0, 20.0, 0.0]


def test_preview_plan_missing_dxf_cannot_execute():
    context = build_style_context()
    plan = build_preview_insert_plan({"entities": []}, None, None, context)
    assert plan["can_execute"] is False
    assert plan["save"] is False
