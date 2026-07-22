from __future__ import annotations

import asyncio

import pytest
from mcp.server.fastmcp import FastMCP

from xicad_mcp.headless_core_batch1 import Approval, Point3D
from xicad_mcp.headless_core_batch24b import (
    AnnotationMode,
    AreaGeometrySnapshot,
    CurveSnapshot,
    HwAreaRequest,
    MakeAreaCenterRequest,
    ProposedAreaBoundary,
    ProposedAreaText,
    ProposedRoomRow,
    ProposedScaledArea,
    ProposedSiteAreaRow,
    ProposedTriangleAnnotation,
    RoomAreaSnapshot,
    RoomTableRequest,
    SameEntityCriteria,
    ScaleAreaRequest,
    SelectableEntitySnapshot,
    SelectSameRequest,
    SiteAreaMode,
    SiteAreaRequest,
    SiteAreaSnapshot,
    TableMode,
    TriangleSnapshot,
    plan_hw_area,
    plan_make_area_center,
    plan_room_table,
    plan_scale_area,
    plan_select_same,
    plan_site_area,
    register_headless_core_batch24b_tools,
)


def point(x: float, y: float = 0, z: float = 0) -> Point3D:
    return Point3D(x=x, y=y, z=z)


def test_hw_validates_triangle_area_and_recovered_output_mode() -> None:
    request = HwAreaRequest(
        document_id="D",
        triangle=TriangleSnapshot(source_id="T1", horizontal_length=6, vertical_length=4, geometry_revision="r1"),
        annotation_mode=AnnotationMode.CREATE_TEXT,
        exact_annotation=ProposedTriangleAnnotation(
            formula_text="6 x 4 / 2",
            result_text="12.00",
            reported_area=12,
            text_height=2.5,
            layer="AREA",
            insertion_point=point(10, 10),
        ),
    )
    assert plan_hw_area(request).computed_area == 12
    with pytest.raises(ValueError, match="reported area"):
        HwAreaRequest.model_validate(
            {**request.model_dump(), "exact_annotation": {**request.exact_annotation.model_dump(), "reported_area": 13}}
        )


def test_mac_accepts_only_explicit_boundaries_and_matching_texts() -> None:
    lines = (
        CurveSnapshot(handle="A", entity_type="LINE", layer="CEN", geometry_revision="r1"),
        CurveSnapshot(handle="B", entity_type="LINE", layer="CEN", geometry_revision="r2"),
    )
    boundary = ProposedAreaBoundary(
        boundary_id="R1",
        source_handles=("A", "B"),
        exact_vertices=(point(0, 0), point(10, 0), point(0, 10)),
        reported_area=50,
        layer="AREA",
    )
    label = ProposedAreaText(boundary_id="R1", text="50.00", insertion_point=point(3, 3), layer="TEXT")
    request = MakeAreaCenterRequest(
        document_id="D",
        centerlines=lines,
        recognition_layer_pattern="CEN*",
        turn_off_other_layers=True,
        output_layer="AREA",
        exact_boundaries=(boundary,),
        write_individual_areas=True,
        exact_area_texts=(label,),
        make_basis_table=True,
        table_mode=TableMode.GENERAL,
        decimal_places=2,
        rounding_policy="반올림",
        input_unit="mm",
    )
    assert plan_make_area_center(request).creates_boundaries == (boundary,)
    with pytest.raises(ValueError, match="one exact area text"):
        MakeAreaCenterRequest.model_validate({**request.model_dump(), "exact_area_texts": []})


def test_mrt_validates_net_area_from_versioned_room_snapshots() -> None:
    room = RoomAreaSnapshot(handle="P1", gross_area=30, excluded_area=6, geometry_revision="r1")
    row = ProposedRoomRow(source_handle="P1", room_number="010", room_name="ROOM", reported_area=24)
    request = RoomTableRequest(
        document_id="D",
        rooms=(room,),
        exact_rows=(row,),
        table_mode=TableMode.CAD,
        live_area_numbers=True,
        output_line_layer="TABLE",
        output_text_layer="TEXT",
        exclusion_layers=("COLUMN",),
        decimal_places=2,
        rounding_policy="반올림",
        comma_grouping=True,
        table_text_height=2.5,
        order_by="Num_rdo",
    )
    assert plan_room_table(request).rows[0].reported_area == 24
    with pytest.raises(ValueError, match="gross minus"):
        RoomTableRequest.model_validate({**request.model_dump(), "exact_rows": [{**row.model_dump(), "reported_area": 25}]})


def test_sar_preserves_recovered_mode_and_validates_numbered_rows() -> None:
    components = (
        SiteAreaSnapshot(component_id="A", reported_area=10, geometry_revision="r1"),
        SiteAreaSnapshot(component_id="B", reported_area=20, geometry_revision="r2"),
    )
    rows = (
        ProposedSiteAreaRow(component_id="A", sequence_number=7, calculation_text="A formula", area=10),
        ProposedSiteAreaRow(component_id="B", sequence_number=8, calculation_text="B formula", area=20),
    )
    request = SiteAreaRequest(
        document_id="D",
        mode=SiteAreaMode.RECTANGLE_AUTO,
        components=components,
        exact_rows=rows,
        starting_number=7,
        unit="m2",
        decimal_places=2,
        ordering_key="OrderPnt4_img",
        ordering_direction="Order1_img",
        ordering_tolerance=50,
        rectangle_tolerance=1,
        delete_generated_boundaries=True,
        display_pyong=False,
        comma_grouping=True,
        geometry_layer="SITE",
        table_layer="TABLE",
        text_layer="TEXT",
    )
    assert plan_site_area(request).mode is SiteAreaMode.RECTANGLE_AUTO
    with pytest.raises(ValueError, match="contiguous numbering"):
        SiteAreaRequest.model_validate(
            {**request.model_dump(), "exact_rows": [rows[0].model_dump(), {**rows[1].model_dump(), "sequence_number": 9}]}
        )


def test_sca_is_explicit_result_only_and_does_not_infer_scale() -> None:
    source = AreaGeometrySnapshot(handle="P", area=100, geometry_revision="r1")
    result = ProposedScaledArea(
        source_handle="P",
        result_area=175,
        exact_vertices=(point(0, 0), point(10, 0), point(0, 35)),
        result_layer="AREA",
    )
    plan = plan_scale_area(
        ScaleAreaRequest(document_id="D", sources=(source,), requested_operation_id="approved-op-7", exact_results=(result,))
    )
    assert plan.results == (result,)
    assert "does not claim legacy equivalence" in plan.semantic_gaps[2]


def entity(handle: str, *, layer: str = "A", text: str | None = None, height: float | None = None) -> SelectableEntitySnapshot:
    return SelectableEntitySnapshot(
        handle=handle,
        entity_type="TEXT",
        layer_name=layer,
        text=text,
        text_style="Standard",
        text_height=height,
        geometry_revision=f"r-{handle}",
    )


def test_se_deterministically_filters_explicit_snapshots_and_area() -> None:
    request = SelectSameRequest(
        document_id="D",
        reference=entity("R", text="ROOM", height=2.5),
        candidates=(
            entity("A", text="ROOM-01", height=2.5005),
            entity("B", text="OTHER", height=2.5),
            entity("C", layer="B", text="ROOM-02", height=2.5),
        ),
        criteria=SameEntityCriteria(layer_name=True, text=True, text_contains=True, text_height_tolerance=0.001),
        selection_area_handles=("A", "B"),
    )
    assert plan_select_same(request).selected_handles == ("A",)
    with pytest.raises(ValueError, match="known candidate"):
        SelectSameRequest.model_validate({**request.model_dump(), "selection_area_handles": ["Z"]})


def test_approval_fingerprint_is_canonical_and_exact() -> None:
    request = ScaleAreaRequest(
        document_id="D",
        sources=(AreaGeometrySnapshot(handle="P", area=1, geometry_revision="r1"),),
        requested_operation_id="op",
        exact_results=(
            ProposedScaledArea(
                source_handle="P",
                result_area=2,
                exact_vertices=(point(0), point(1), point(0, 1)),
                result_layer="0",
            ),
        ),
    )
    invalid = request.model_copy(
        update={"dry_run": False, "approval": Approval(approved=True, fingerprint="sha256:wrong")}
    ).model_dump()
    with pytest.raises(ValueError, match="exact approval"):
        ScaleAreaRequest.model_validate(invalid)
    approved = ScaleAreaRequest.model_validate(
        request.model_copy(
            update={"dry_run": False, "approval": Approval(approved=True, fingerprint=request.fingerprint())}
        ).model_dump()
    )
    assert not plan_scale_area(approved).dry_run


def test_registers_six_read_only_tools() -> None:
    mcp = FastMCP("batch24b")
    register_headless_core_batch24b_tools(mcp)
    tools = asyncio.run(mcp.list_tools())
    assert {tool.name for tool in tools} == {
        "xicad_plan_hw",
        "xicad_plan_mac",
        "xicad_plan_mrt",
        "xicad_plan_sar",
        "xicad_plan_sca",
        "xicad_plan_se",
    }
    assert all(tool.annotations and tool.annotations.readOnlyHint for tool in tools)
    assert all(tool.annotations and not tool.annotations.destructiveHint for tool in tools)
