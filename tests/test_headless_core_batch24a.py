import asyncio

import pytest
from mcp.server.fastmcp import FastMCP

from xicad_mcp.headless_core_batch1 import Approval, Point3D
from xicad_mcp.headless_core_batch24a import (
    AreaFieldTarget,
    DistanceMemoryRequest,
    DynamicAreaRequest,
    EnergyElevationRequest,
    ExactGraphic,
    FieldRelationSnapshot,
    FindFieldObjectsRequest,
    GraphicKind,
    NorthHeightStandard,
    NorthReviewMode,
    NorthReviewRequest,
    PolylineLengthSnapshot,
    RectangleAreaLabelRequest,
    RectangleSnapshot,
    RoundingPolicy,
    TextAnchor,
    plan_check_dist_north,
    plan_distance_memory,
    plan_draw_energy_elevation,
    plan_dynamic_area,
    plan_find_field_objects,
    plan_rectangle_area_label,
    register_headless_core_batch24a_tools,
)


def _line(layer: str = "CHECK") -> ExactGraphic:
    return ExactGraphic(
        kind=GraphicKind.LINE,
        points=(Point3D(x=0, y=0), Point3D(x=10, y=5)),
        layer=layer,
    )


def test_cdn_preserves_reviewed_geometry_and_requires_mode_specific_inputs() -> None:
    request = NorthReviewRequest(
        document_id="D",
        mode=NorthReviewMode.PLAN,
        height_standard=NorthHeightStandard.TEN_METERS,
        limit_distance_m=10,
        result_layer="CHECK",
        plan_spacing_m=1.5,
        exact_review_graphics=(_line(),),
    )
    plan = plan_check_dist_north(request)
    assert plan.creates == request.exact_review_graphics
    assert plan.plan_spacing_m == 1.5
    with pytest.raises(ValueError, match="plan_spacing_m"):
        NorthReviewRequest(
            document_id="D",
            mode=NorthReviewMode.PLAN,
            height_standard=NorthHeightStandard.NINE_METERS,
            limit_distance_m=9,
            result_layer="CHECK",
            exact_review_graphics=(_line(),),
        )


def test_dar_requires_exact_field_expression_and_preserves_source_binding() -> None:
    plan = plan_dynamic_area(
        DynamicAreaRequest(
            document_id="D",
            targets=(
                AreaFieldTarget(
                    source_handle="A1",
                    verified_area=24,
                    exact_field_expression="%<exact-cad-field>%",
                    insertion_point=Point3D(x=5, y=6),
                    layer="AREA",
                    text_height=2.5,
                    prefix="AREA: ",
                    suffix=" m2",
                ),
            ),
        )
    )
    assert plan.creates[0].source_handle == "A1"
    assert plan.creates[0].field_expression == "%<exact-cad-field>%"
    assert plan.creates[0].display_template == "AREA: {FIELD} m2"


def test_dee_is_an_exact_geometry_pass_through_not_an_invented_calculator() -> None:
    graphics = (_line("ENERGY"),)
    plan = plan_draw_energy_elevation(
        EnergyElevationRequest(
            document_id="D",
            standard_reference="reviewed-standard-v1",
            source_evidence_handles=("WALL-1", "OPENING-1"),
            exact_elevation_graphics=graphics,
        )
    )
    assert plan.creates == graphics
    assert "calculation" in plan.semantic_gaps[0] or "interpretation" in plan.semantic_gaps[0]


def test_dm_serializes_explicit_snapshot_with_deterministic_half_up_rounding() -> None:
    plan = plan_distance_memory(
        DistanceMemoryRequest(
            document_id="D",
            polyline=PolylineLengthSnapshot(polyline_handle="P1", measured_length=1234.5),
            memory_slot="distance-memory",
            unit_multiplier=0.001,
            decimal_places=3,
        )
    )
    assert plan.numeric_value == pytest.approx(1.2345)
    assert plan.serialized_value == "1.235"


def test_ffo_compares_explicit_relations_to_existing_object_snapshot() -> None:
    plan = plan_find_field_objects(
        FindFieldObjectsRequest(
            document_id="D",
            fields=(
                FieldRelationSnapshot(
                    field_owner_handle="T1",
                    exact_field_expression="FIELD",
                    related_object_handles=("A", "B"),
                ),
            ),
            existing_object_handles=("a", "C"),
        )
    )
    assert plan.findings[0].found_handles == ("A",)
    assert plan.findings[0].missing_handles == ("B",)
    assert plan.highlight_handles == ("A",)


def test_hv_formats_explicit_rectangle_dimensions_area_and_dcl_options() -> None:
    plan = plan_rectangle_area_label(
        RectangleAreaLabelRequest(
            document_id="D",
            rectangles=(RectangleSnapshot(source_handle="R1", width=2400, height=3600),),
            dimension_multiplier=0.001,
            decimal_places=2,
            rounding=RoundingPolicy.NEAREST,
            dimension_unit_text="m",
            show_result=True,
            show_brackets=True,
            lower_text="ROOM",
            insertion_point=Point3D(x=100, y=200),
            anchor=TextAnchor.MIDDLE_CENTER,
            layer="AREA",
            text_height=250,
        )
    )
    assert plan.labels[0].converted_width == "2.40"
    assert plan.labels[0].converted_height == "3.60"
    assert plan.labels[0].converted_area == "8.64"
    assert plan.labels[0].text == "(2.40m x 3.60m = 8.64m²)\nROOM"


def test_non_dry_run_requires_exact_canonical_fingerprint() -> None:
    draft = DistanceMemoryRequest(
        document_id="D",
        polyline=PolylineLengthSnapshot(polyline_handle="P1", measured_length=10),
        memory_slot="slot",
    )
    with pytest.raises(ValueError, match="exact approval fingerprint"):
        DistanceMemoryRequest(
            document_id="D",
            polyline=draft.polyline,
            memory_slot="slot",
            dry_run=False,
            approval=Approval(approved=True, fingerprint="sha256:wrong"),
        )
    approved = DistanceMemoryRequest(
        document_id="D",
        polyline=draft.polyline,
        memory_slot="slot",
        dry_run=False,
        approval=Approval(approved=True, fingerprint=draft.fingerprint()),
    )
    assert not approved.dry_run


def test_registers_six_read_only_tools() -> None:
    mcp = FastMCP("batch24a-test")
    register_headless_core_batch24a_tools(mcp)
    tools = asyncio.run(mcp.list_tools())
    assert len(tools) == 6
    assert all(tool.annotations and tool.annotations.readOnlyHint for tool in tools)
    assert all(tool.annotations and not tool.annotations.destructiveHint for tool in tools)
