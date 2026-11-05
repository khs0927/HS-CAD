import asyncio

import pytest
from mcp.server.fastmcp import FastMCP

from xicad_mcp.headless_core_batch1 import Approval, Point3D
from xicad_mcp.headless_core_batch25a import (
    CommonTextRequest,
    EnergyAreaTableRequest,
    ExactGraphic,
    ExactGraphicKind,
    NumberedPlacement,
    NumericTextSnapshot,
    ObjectTextTarget,
    SlopeFormat,
    SlopeRequest,
    SpecialCharacterRequest,
    TextOnObjectRequest,
    TextPointIncrementRequest,
    plan_common_text,
    plan_energy_area_table,
    plan_slope,
    plan_special_character,
    plan_text_on_object,
    plan_text_point_increment,
    register_headless_core_batch25a_tools,
)


def test_sl_formats_recovered_percent_policy_and_angle() -> None:
    plan = plan_slope(
        SlopeRequest(
            document_id="D", start=Point3D(x=0, y=0), end=Point3D(x=10, y=2),
            format=SlopeFormat.PERCENT, decimal_places=1, prefix="S=",
            text_insertion_point=Point3D(x=4, y=2), layer="SLOPE", text_height=250,
            triangle_vertices=(Point3D(x=0, y=0), Point3D(x=10, y=0), Point3D(x=10, y=2)),
        )
    )
    assert plan.legacy_symbol == "xiSLOPE"
    assert plan.text.text == "S=20.0%"
    assert plan.text.rotation_degrees == pytest.approx(11.309932)
    with pytest.raises(ValueError, match="horizontal run"):
        SlopeRequest(document_id="D", start=Point3D(x=0, y=0), end=Point3D(x=0, y=2), format=SlopeFormat.PERCENT, text_insertion_point=Point3D(x=0, y=0), layer="0", text_height=1)


def test_zae_passes_reviewed_graphics_without_inventing_area_rules() -> None:
    graphic = ExactGraphic(kind=ExactGraphicKind.TEXT, layer="TABLE", points=(Point3D(x=0, y=0),), text="24.0", text_height=250)
    plan = plan_energy_area_table(EnergyAreaTableRequest(document_id="D", source_handles=("A1",), result_with_legend=True, unit_placement="table_top", elevation_table_scale=1, plan_table_scale=1, excluded_layers=("VOID",), exact_graphics=(graphic,)))
    assert plan.creates == (graphic,)
    assert "summation" in plan.semantic_gaps[0]


def test_qt_preserves_explicit_common_text_catalog_selection() -> None:
    plan = plan_common_text(CommonTextRequest(document_id="D", catalog_group=3, catalog_index=2, catalog_text="철물", insertion_point=Point3D(x=1, y=2), layer="TEXT", text_height=300))
    assert plan.catalog_group == 3
    assert plan.create.text == "철물"


def test_qw_takes_explicit_unicode_not_opaque_exe_protocol() -> None:
    plan = plan_special_character(SpecialCharacterRequest(document_id="D", characters="±Ø", insertion_point=Point3D(x=1, y=2), layer="TEXT", text_height=300))
    assert plan.create.text == "±Ø"
    assert "external-program" in plan.semantic_gaps[0]


def test_tip_generates_positioned_incremented_text_with_zero_padding() -> None:
    def placement(x: float) -> NumberedPlacement:
        return NumberedPlacement(
            insertion_point=Point3D(x=x, y=0), layer="NUM", text_height=200
        )

    plan = plan_text_point_increment(TextPointIncrementRequest(document_id="D", source=NumericTextSnapshot(source_handle="T1", prefix="A-", value=7, suffix="F", minimum_digits=3), increment=2, placements=(placement(1), placement(2))))
    assert tuple(item.text for item in plan.creates) == ("A-009F", "A-011F")


def test_too_uses_adapter_anchor_and_tangent_snapshot() -> None:
    plan = plan_text_on_object(TextOnObjectRequest(document_id="D", text="WALL", targets=(ObjectTextTarget(object_handle="L1", anchor=Point3D(x=10, y=20), tangent_degrees=0),), normal_offset=5, layer="ANNO", text_height=250))
    assert plan.creates[0].insertion_point == Point3D(x=10, y=25, z=0)
    assert plan.creates[0].rotation_degrees == 0


def test_non_dry_run_requires_exact_canonical_fingerprint() -> None:
    draft = SpecialCharacterRequest(document_id="D", characters="±", insertion_point=Point3D(x=0, y=0), layer="0", text_height=1)
    with pytest.raises(ValueError, match="exact approval fingerprint"):
        SpecialCharacterRequest(document_id="D", characters="±", insertion_point=Point3D(x=0, y=0), layer="0", text_height=1, dry_run=False, approval=Approval(approved=True, fingerprint="sha256:wrong"))
    approved = SpecialCharacterRequest(document_id="D", characters="±", insertion_point=Point3D(x=0, y=0), layer="0", text_height=1, dry_run=False, approval=Approval(approved=True, fingerprint=draft.fingerprint()))
    assert not approved.dry_run


def test_registers_six_read_only_tools() -> None:
    mcp = FastMCP("batch25a-test")
    register_headless_core_batch25a_tools(mcp)
    tools = asyncio.run(mcp.list_tools())
    assert len(tools) == 6
    assert all(tool.annotations and tool.annotations.readOnlyHint for tool in tools)
    assert all(tool.annotations and not tool.annotations.destructiveHint for tool in tools)
