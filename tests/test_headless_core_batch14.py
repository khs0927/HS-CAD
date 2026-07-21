import asyncio

import pytest
from mcp.server.fastmcp import FastMCP

from xicad_mcp.headless_core_batch1 import Point3D
from xicad_mcp.headless_core_batch14 import (
    BreakPolylineRequest,
    EndpointEditRequest,
    EndpointOperation,
    ExplodePolicy,
    ExtendSide,
    GeometrySnapshot,
    HandleRequest,
    KMarkRequest,
    LineExplodeRequest,
    LineExportRequest,
    PolylineEditMode,
    PolylineEditRequest,
    PolylineExtendRequest,
    PolylineToCircleRequest,
    ProjectionAxis,
    ProjectRequest,
    RectangleRequest,
    SourceDisposition,
    plan_break_polyline,
    plan_endpoint_edit,
    plan_k_mark,
    plan_line_explode,
    plan_line_export,
    plan_polyline_edit,
    plan_polyline_extend,
    plan_polyline_reverse,
    plan_polyline_to_circle,
    plan_project,
    plan_rectangle,
    register_headless_core_batch14_tools,
)


def geometry(handle: str = "A", vertices: tuple[Point3D, ...] | None = None) -> GeometrySnapshot:
    return GeometrySnapshot(
        handle=handle,
        entity_type="LWPOLYLINE",
        vertices=vertices or (Point3D(x=0, y=0), Point3D(x=2, y=0), Point3D(x=2, y=2)),
        layer="G",
    )


def test_k_creates_three_rotated_strokes() -> None:
    plan = plan_k_mark(
        KMarkRequest(
            document_id="D",
            insertion_points=(Point3D(x=10, y=10),),
            size=2,
            rotation_degrees=90,
            layer="SYM",
        )
    )
    assert len(plan.creates[0].strokes) == 3
    assert plan.creates[0].layer == "SYM"


def test_lex_returns_normalized_data_without_file_io() -> None:
    plan = plan_line_export(
        LineExportRequest(
            document_id="D",
            target_handles=("A",),
            origin=Point3D(x=0, y=0),
            normalize_scale=True,
            include_layer=False,
        ),
        (geometry(),),
    )
    assert plan.exports[0].relative_vertices[-1] == Point3D(x=1, y=1, z=0)
    assert plan.exports[0].layer is None


def test_lxp_decomposes_vertices_and_marks_replace() -> None:
    plan = plan_line_explode(
        LineExplodeRequest(
            document_id="D",
            target_handles=("A",),
            policy=ExplodePolicy.LINE_SEGMENTS,
            source_disposition=SourceDisposition.REPLACE,
            target_layer="OUT",
        ),
        (geometry(),),
    )
    assert len(plan.creates) == 2
    assert plan.delete_handles == ("A",)


def test_lxp_blocks_unmodelled_arc_semantics() -> None:
    with pytest.raises(ValueError, match="bulge"):
        LineExplodeRequest(
            document_id="D",
            target_handles=("A",),
            policy=ExplodePolicy.PRESERVE_ARCS,
            source_disposition=SourceDisposition.PRESERVE,
            target_layer="OUT",
        )


def test_me_endpoint_operation_is_explicit() -> None:
    plan = plan_endpoint_edit(
        EndpointEditRequest(
            document_id="D",
            target_handle="A",
            operation=EndpointOperation.EXTEND_START,
            target_point=Point3D(x=-1, y=0),
        ),
        (geometry(),),
    )
    assert plan.target_vertices["A"][0].x == -1
    assert plan.legacy_symbol == "unresolved:ME"


def test_p2c_computes_circumcircle() -> None:
    source = geometry(vertices=(Point3D(x=1, y=0), Point3D(x=0, y=1), Point3D(x=-1, y=0)))
    plan = plan_polyline_to_circle(
        PolylineToCircleRequest(
            document_id="D",
            source_handle="A",
            sample_indices=(0, 1, 2),
            source_disposition=SourceDisposition.PRESERVE,
            target_layer="CIRCLE",
        ),
        (source,),
    )
    assert plan.create.center == Point3D(x=0, y=0, z=0)
    assert plan.create.radius == pytest.approx(1)


def test_p2c_rejects_collinear_points() -> None:
    with pytest.raises(ValueError, match="collinear"):
        plan_polyline_to_circle(
            PolylineToCircleRequest(
                document_id="D",
                source_handle="A",
                sample_indices=(0, 1, 2),
                source_disposition=SourceDisposition.PRESERVE,
                target_layer="C",
            ),
            (
                geometry(
                    vertices=(
                        Point3D(x=0, y=0),
                        Point3D(x=1, y=0),
                        Point3D(x=2, y=0),
                    )
                ),
            ),
        )


def test_pe_requires_mode_specific_value() -> None:
    with pytest.raises(ValueError, match="width"):
        PolylineEditRequest(
            document_id="D",
            target_handles=("A",),
            mode=PolylineEditMode.SET_WIDTH,
        )
    plan = plan_polyline_edit(
        PolylineEditRequest(
            document_id="D",
            target_handles=("A",),
            mode=PolylineEditMode.SET_WIDTH,
            width=3,
        ),
        (geometry(),),
    )
    assert plan.edits[0].width == 3


def test_plb_and_plbc_share_explicit_close_policy() -> None:
    open_plan = plan_break_polyline(
        BreakPolylineRequest(
            document_id="D",
            source_handle="A",
            break_after_index=0,
            close_outputs=False,
            source_disposition=SourceDisposition.REPLACE,
        ),
        (geometry(),),
    )
    closed_plan = plan_break_polyline(
        BreakPolylineRequest(
            document_id="D",
            source_handle="A",
            break_after_index=0,
            close_outputs=True,
            source_disposition=SourceDisposition.PRESERVE,
        ),
        (geometry(),),
    )
    assert open_plan.command_alias == "PLB" and not open_plan.outputs_closed
    assert closed_plan.command_alias == "PLBC" and closed_plan.outputs_closed


def test_ple_extends_selected_side() -> None:
    plan = plan_polyline_extend(
        PolylineExtendRequest(
            document_id="D",
            source_handle="A",
            side=ExtendSide.END,
            extension_points=(Point3D(x=4, y=2),),
        ),
        (geometry(),),
    )
    assert plan.target_vertices["A"][-1].x == 4


def test_plr_reverses_vertex_order() -> None:
    plan = plan_polyline_reverse(HandleRequest(document_id="D", target_handles=("A",)), (geometry(),))
    assert plan.target_vertices["A"][0] == Point3D(x=2, y=2, z=0)


def test_pr_projects_to_explicit_plane() -> None:
    plan = plan_project(
        ProjectRequest(
            document_id="D",
            target_handles=("A",),
            plane=ProjectionAxis.YZ,
            offset=7,
        ),
        (geometry(),),
    )
    assert all(point.x == 7 for point in plan.target_vertices["A"])


def test_rec_builds_four_rotated_vertices() -> None:
    plan = plan_rectangle(
        RectangleRequest(
            document_id="D",
            center=Point3D(x=0, y=0),
            width=4,
            height=2,
            rotation_degrees=0,
            layer="R",
        )
    )
    assert plan.vertices[0] == Point3D(x=-2, y=-1, z=0)
    assert len(plan.vertices) == 4


def test_live_request_requires_approval_fingerprint() -> None:
    with pytest.raises(ValueError, match="approval fingerprint"):
        RectangleRequest(
            document_id="D",
            center=Point3D(x=0, y=0),
            width=1,
            height=1,
            layer="R",
            dry_run=False,
        )


def test_registers_12_read_only_tools_with_fastmcp() -> None:
    mcp = FastMCP("batch14-test")
    register_headless_core_batch14_tools(mcp)
    tools = asyncio.run(mcp.list_tools())
    assert len(tools) == 12
    assert {tool.name for tool in tools} == {
        "xicad_plan_k",
        "xicad_plan_lex",
        "xicad_plan_lxp",
        "xicad_plan_me",
        "xicad_plan_p2c",
        "xicad_plan_pe",
        "xicad_plan_plb",
        "xicad_plan_plbc",
        "xicad_plan_ple",
        "xicad_plan_plr",
        "xicad_plan_pr",
        "xicad_plan_rec",
    }
    assert all(tool.annotations and tool.annotations.readOnlyHint for tool in tools)
