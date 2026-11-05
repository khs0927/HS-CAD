from __future__ import annotations

import asyncio

import pytest
from mcp.server.fastmcp import FastMCP

from xicad_mcp.headless_core_batch1 import Approval, Point3D
from xicad_mcp.headless_core_batch26b import (
    PolylineSnapshot,
    PolylineWidthOutlineRequest,
    PolylineWidthResult,
    PrimitiveKind,
    ProposedCurvePrimitive,
    ProposedPolyline,
    RoundSurfaceRequest,
    SolidRectangleRequest,
    ThreePointRectangleRequest,
    UnfoldedPolylineResult,
    UnfoldPolylineRequest,
    VSymbolRequest,
    plan_polyline_width_outline,
    plan_round_surface,
    plan_solid_rectangle,
    plan_three_point_rectangle,
    plan_unfold_polyline,
    plan_v_symbol,
    register_headless_core_batch26b_tools,
)


def point(x: float, y: float = 0, z: float = 0) -> Point3D:
    return Point3D(x=x, y=y, z=z)


def test_pwd_requires_one_exact_wide_polyline_and_closed_outlines_per_source() -> None:
    source = PolylineSnapshot(handle="P1", vertices=(point(0), point(10)), closed=False, geometry_revision="r1")
    wide = ProposedPolyline(vertices=source.vertices, closed=False, layer="WIDE", constant_width=2)
    outline = ProposedPolyline(
        vertices=(point(0, -1), point(10, -1), point(10, 1), point(0, 1)), closed=True, layer="OUT"
    )
    result = PolylineWidthResult(
        source_handle="P1", requested_width=2, wide_polyline=wide, exact_outline_loops=(outline,)
    )
    plan = plan_polyline_width_outline(
        PolylineWidthOutlineRequest(document_id="D", sources=(source,), exact_results=(result,))
    )
    assert plan.results == (result,)
    with pytest.raises(ValueError, match="exact requested width"):
        PolylineWidthResult.model_validate({**result.model_dump(), "requested_width": 3})


def test_r3_accepts_only_explicit_four_vertex_closed_result() -> None:
    rectangle = ProposedPolyline(
        vertices=(point(0, 0), point(4, 0), point(4, 2), point(0, 2)), closed=True, layer="RECT"
    )
    request = ThreePointRectangleRequest(
        document_id="D", picked_points=(point(0, 0), point(4, 0), point(4, 2)), exact_rectangle=rectangle
    )
    assert plan_three_point_rectangle(request).rectangle == rectangle
    with pytest.raises(ValueError, match="four-vertex closed"):
        ThreePointRectangleRequest.model_validate(
            {**request.model_dump(), "exact_rectangle": {**rectangle.model_dump(), "closed": False}}
        )


def test_rnd_carries_only_exact_typed_curve_components() -> None:
    component = ProposedCurvePrimitive(
        kind=PrimitiveKind.ARC,
        exact_control_points=(point(0), point(5, 2), point(10)),
        layer="ROUND",
    )
    plan = plan_round_surface(
        RoundSurfaceRequest(
            document_id="D", anchor_points=(point(0), point(10)), exact_components=(component,)
        )
    )
    assert plan.components == (component,)
    assert "does not claim legacy equivalence" in plan.semantic_gaps[2]


def test_rs_preserves_exact_four_solid_vertices_and_properties() -> None:
    request = SolidRectangleRequest(
        document_id="D",
        picked_points=(point(0), point(3, 2)),
        exact_solid_vertices=(point(0, 0), point(0, 2), point(3, 0), point(3, 2)),
        layer="SOLID",
        color_index=7,
    )
    plan = plan_solid_rectangle(request)
    assert plan.solid_vertices == request.exact_solid_vertices
    assert plan.color_index == 7


def test_ufd_validates_one_to_one_results_and_each_segment_length() -> None:
    source = PolylineSnapshot(
        handle="P", vertices=(point(0, 0), point(3, 0), point(3, 4)), closed=False, geometry_revision="r1"
    )
    result = UnfoldedPolylineResult(
        source_handle="P", exact_vertices=(point(10), point(13), point(17)), layer="UNFOLD"
    )
    request = UnfoldPolylineRequest(document_id="D", sources=(source,), exact_results=(result,))
    assert plan_unfold_polyline(request).results == (result,)
    with pytest.raises(ValueError, match="preserve each source segment length"):
        UnfoldPolylineRequest.model_validate(
            {
                **request.model_dump(),
                "exact_results": [
                    {"source_handle": "P", "exact_vertices": [point(10), point(13), point(18)], "layer": "UNFOLD"}
                ],
            }
        )


def test_v_requires_explicit_non_collinear_left_tip_right_vertices() -> None:
    request = VSymbolRequest(document_id="D", exact_vertices=(point(0, 2), point(1, 0), point(2, 2)), layer="SYM")
    assert plan_v_symbol(request).vertices[1] == point(1, 0)
    with pytest.raises(ValueError, match="non-collinear"):
        VSymbolRequest(document_id="D", exact_vertices=(point(0), point(1), point(2)), layer="SYM")


def test_approval_fingerprint_is_canonical_and_exact() -> None:
    request = VSymbolRequest(document_id="D", exact_vertices=(point(0, 2), point(1, 0), point(2, 2)), layer="SYM")
    with pytest.raises(ValueError, match="exact approval"):
        VSymbolRequest.model_validate(
            request.model_copy(
                update={"dry_run": False, "approval": Approval(approved=True, fingerprint="sha256:wrong")}
            ).model_dump()
        )
    approved = VSymbolRequest.model_validate(
        request.model_copy(
            update={"dry_run": False, "approval": Approval(approved=True, fingerprint=request.fingerprint())}
        ).model_dump()
    )
    assert not plan_v_symbol(approved).dry_run


def test_registers_six_read_only_tools() -> None:
    mcp = FastMCP("batch26b")
    register_headless_core_batch26b_tools(mcp)
    tools = asyncio.run(mcp.list_tools())
    assert {tool.name for tool in tools} == {
        "xicad_plan_pwd",
        "xicad_plan_r3",
        "xicad_plan_rnd",
        "xicad_plan_rs",
        "xicad_plan_ufd",
        "xicad_plan_v",
    }
    assert all(tool.annotations and tool.annotations.readOnlyHint for tool in tools)
    assert all(tool.annotations and not tool.annotations.destructiveHint for tool in tools)
