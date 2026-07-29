from __future__ import annotations

import asyncio
import math

import pytest
from mcp.server.fastmcp import FastMCP

from xicad_mcp.headless_core_batch1 import Approval, Point3D
from xicad_mcp.headless_core_batch25b import (
    BoundingBoxRequest,
    CurveTangentSnapshot,
    EntityExtentsSnapshot,
    LinetypeTextElement,
    MakeTextLinetypeRequest,
    MaskMode,
    OpenPolylineSnapshot,
    PerpendicularCurveRequest,
    PolylineCloseRequest,
    ProposedLinetype,
    ProposedTableCell,
    ProposedTextBoundary,
    TableResultMode,
    TableTextSnapshot,
    TextBoxRequest,
    TextBoxShape,
    TextCoordinateMode,
    TextEntitySnapshot,
    TextsToTableRequest,
    WorkspaceMode,
    plan_bounding_box,
    plan_make_text_linetype,
    plan_perpendicular_curve,
    plan_polyline_close,
    plan_text_box,
    plan_texts_to_table,
    register_headless_core_batch25b_tools,
)


def point(x: float, y: float = 0, z: float = 0) -> Point3D:
    return Point3D(x=x, y=y, z=z)


def test_ttt_preserves_recovered_choices_and_exact_cell_mapping() -> None:
    source = TableTextSnapshot(
        handle="T1", text="ROOM", insertion_point=point(10, 20), space="model", geometry_revision="r1"
    )
    request = TextsToTableRequest(
        document_id="D",
        result_mode=TableResultMode.CAD_TABLE,
        coordinate_mode=TextCoordinateMode.FRAME_RELATIVE,
        workspace=WorkspaceMode.MODEL,
        frame_handle="F1",
        ordering_anchor="OrderPnt1_img",
        ordering_direction="Order2_img",
        ordering_tolerance=10,
        selection_order_first=False,
        source_texts=(source,),
        exact_cells=(ProposedTableCell(source_handle="T1", row=0, column=0, text="ROOM"),),
        output_line_layer="TABLE",
        output_text_layer="TEXT",
        table_text_height=3,
    )
    assert plan_texts_to_table(request).cells[0].text == "ROOM"
    with pytest.raises(ValueError, match="preserve"):
        TextsToTableRequest.model_validate(
            {**request.model_dump(), "exact_cells": [{"source_handle": "T1", "row": 0, "column": 0, "text": "X"}]}
        )


def test_ttt_rejects_workspace_and_coordinate_contradictions() -> None:
    payload = {
        "document_id": "D",
        "result_mode": "Table_rdo",
        "coordinate_mode": "Absolute_rdo",
        "workspace": "WorkModel_rdo",
        "frame_handle": "unexpected",
        "ordering_anchor": "OrderPnt1_img",
        "ordering_direction": "Order1_img",
        "ordering_tolerance": 0,
        "selection_order_first": True,
        "source_texts": [{"handle": "T", "text": "A", "insertion_point": point(0), "space": "model", "geometry_revision": "r"}],
        "exact_cells": [{"source_handle": "T", "row": 0, "column": 0, "text": "A"}],
        "output_line_layer": "0",
        "output_text_layer": "0",
        "table_text_height": 1,
    }
    with pytest.raises(ValueError, match="does not accept"):
        TextsToTableRequest.model_validate(payload)


def test_tx_requires_exact_geometry_and_consistent_recovered_options() -> None:
    source = TextEntitySnapshot(
        handle="T", text="A", bounds_min=point(0, 0), bounds_max=point(4, 2), geometry_revision="r1"
    )
    boundary = ProposedTextBoundary(
        source_handle="T",
        exact_vertices=(point(-1, -1), point(5, -1), point(5, 3), point(-1, 3)),
        boundary_layer="BOX",
        group_id="G1",
    )
    request = TextBoxRequest(
        document_id="D",
        sources=(source,),
        shape=TextBoxShape.POLYGON,
        polygon_sides=4,
        uppercase=False,
        group_results=True,
        mask_mode=MaskMode.SOLID,
        solid_color=254,
        text_style="Standard",
        text_layer="TEXT",
        text_height=2.5,
        boundary_layer="BOX",
        width_gap=1,
        height_gap=1,
        corner_radius=0,
        exact_boundaries=(boundary,),
    )
    assert plan_text_box(request).boundaries == (boundary,)
    with pytest.raises(ValueError, match="polygon"):
        TextBoxRequest.model_validate({**request.model_dump(), "polygon_sides": None})


def test_mtlt_carries_only_caller_supplied_linetype_definition() -> None:
    definition = ProposedLinetype(
        name="GAS",
        description="gas line",
        dash_pattern=(10, -2, 0, -2),
        text_elements=(
            LinetypeTextElement(text="GAS", style="Standard", scale=1, rotation_degrees=0, x_offset=0, y_offset=0),
        ),
        target_lin_file="approved.lin",
    )
    plan = plan_make_text_linetype(
        MakeTextLinetypeRequest(document_id="D", proposed_linetype=definition, overwrite_existing=False)
    )
    assert plan.proposed_linetype == definition
    assert "does not claim legacy equivalence" in plan.semantic_gaps[2]


def test_pbb_computes_union_from_versioned_extents_in_one_coordinate_system() -> None:
    request = BoundingBoxRequest(
        document_id="D",
        entities=(
            EntityExtentsSnapshot(handle="A", minimum=point(0, 1, 2), maximum=point(4, 5, 6), coordinate_system_id="WCS", geometry_revision="r1"),
            EntityExtentsSnapshot(handle="B", minimum=point(-2, 3, 1), maximum=point(8, 9, 4), coordinate_system_id="WCS", geometry_revision="r2"),
        ),
        output_layer="BOX",
    )
    plan = plan_bounding_box(request)
    assert plan.minimum == point(-2, 1, 1)
    assert plan.maximum == point(8, 9, 6)
    assert plan.vertices[2] == point(8, 9, 1)
    with pytest.raises(ValueError, match="one explicit coordinate system"):
        BoundingBoxRequest.model_validate(
            {**request.model_dump(), "entities": [request.entities[0].model_dump(), {**request.entities[1].model_dump(), "coordinate_system_id": "UCS"}]}
        )


def test_pc_closes_only_open_polylines_with_explicit_flag_policy() -> None:
    source = OpenPolylineSnapshot(
        handle="P", entity_type="LWPOLYLINE", vertices=(point(0), point(1), point(1, 1)), geometry_revision="r1"
    )
    plan = plan_polyline_close(PolylineCloseRequest(document_id="D", polylines=(source,)))
    assert plan.updates[0].vertices == source.vertices
    assert plan.updates[0].set_closed
    with pytest.raises(ValueError, match="only an open"):
        OpenPolylineSnapshot.model_validate({**source.model_dump(), "is_closed": True})


def test_pec_builds_normal_from_versioned_tangent_and_explicit_lengths() -> None:
    source = CurveTangentSnapshot(
        handle="C", base_point=point(10, 20, 3), tangent_x=3, tangent_y=4, geometry_revision="r1"
    )
    plan = plan_perpendicular_curve(
        PerpendicularCurveRequest(
            document_id="D", curves=(source,), negative_length=5, positive_length=10, output_layer="PERP"
        )
    )
    line = plan.lines[0]
    assert math.isclose(line.start_point.x, 14)
    assert math.isclose(line.start_point.y, 17)
    assert math.isclose(line.end_point.x, 2)
    assert math.isclose(line.end_point.y, 26)
    assert line.start_point.z == line.end_point.z == 3


def test_approval_fingerprint_is_canonical_and_exact() -> None:
    source = OpenPolylineSnapshot(
        handle="P", entity_type="POLYLINE", vertices=(point(0), point(1)), geometry_revision="r1"
    )
    request = PolylineCloseRequest(document_id="D", polylines=(source,))
    with pytest.raises(ValueError, match="exact approval"):
        PolylineCloseRequest.model_validate(
            request.model_copy(
                update={"dry_run": False, "approval": Approval(approved=True, fingerprint="sha256:wrong")}
            ).model_dump()
        )
    approved = PolylineCloseRequest.model_validate(
        request.model_copy(
            update={"dry_run": False, "approval": Approval(approved=True, fingerprint=request.fingerprint())}
        ).model_dump()
    )
    assert not plan_polyline_close(approved).dry_run


def test_registers_six_read_only_tools() -> None:
    mcp = FastMCP("batch25b")
    register_headless_core_batch25b_tools(mcp)
    tools = asyncio.run(mcp.list_tools())
    assert {tool.name for tool in tools} == {
        "xicad_plan_ttt",
        "xicad_plan_tx",
        "xicad_plan_mtlt",
        "xicad_plan_pbb",
        "xicad_plan_pc",
        "xicad_plan_pec",
    }
    assert all(tool.annotations and tool.annotations.readOnlyHint for tool in tools)
    assert all(tool.annotations and not tool.annotations.destructiveHint for tool in tools)
