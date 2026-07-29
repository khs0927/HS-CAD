import asyncio

import pytest
from mcp.server.fastmcp import FastMCP

from xicad_mcp.headless_core_batch1 import Point3D
from xicad_mcp.headless_core_batch21a import (
    DistanceDivisionMode,
    DivideArcCopyRequest,
    DivideCopyRequest,
    ExtendLineRequest,
    JoinLineRequest,
    LineAnchor,
    LineSnapshot,
    MlineConvertRequest,
    MlineSnapshot,
    MultiCopyRequest,
    plan_divide_arc_copy,
    plan_divide_copy,
    plan_extend_line,
    plan_join_line,
    plan_mline_convert,
    plan_multi_copy,
    register_headless_core_batch21a_tools,
)


def line(handle: str, start: Point3D | None = None, end: Point3D | None = None) -> LineSnapshot:
    return LineSnapshot(handle=handle, start=start or Point3D(x=0, y=0), end=end or Point3D(x=10, y=0), layer="L")


def test_dac_explicit_endpoint_policy() -> None:
    plan = plan_divide_arc_copy(
        DivideArcCopyRequest(
            document_id="D",
            source_handles=("A",),
            center=Point3D(x=0, y=0),
            start_angle_degrees=0,
            end_angle_degrees=90,
            division_count=3,
            include_start=False,
            include_end=True,
        )
    )
    assert [item.rotation_degrees for item in plan.transforms] == [30, 60, 90]


def test_dvc_count_and_spacing_modes() -> None:
    count = plan_divide_copy(
        DivideCopyRequest(
            document_id="D",
            source_handles=("A",),
            path_start=Point3D(x=0, y=0),
            path_end=Point3D(x=10, y=0),
            mode=DistanceDivisionMode.COUNT,
            division_count=2,
            include_start=False,
            include_end=True,
        )
    )
    assert [item.translation.x for item in count.transforms] == [5, 10]
    spacing = plan_divide_copy(
        DivideCopyRequest(
            document_id="D",
            source_handles=("A",),
            path_start=Point3D(x=0, y=0),
            path_end=Point3D(x=10, y=0),
            mode=DistanceDivisionMode.SPACING,
            spacing=2.5,
            include_start=False,
            include_end=True,
        )
    )
    assert len(spacing.transforms) == 4


def test_exl_adjusts_straight_line_around_anchor() -> None:
    plan = plan_extend_line(
        ExtendLineRequest(document_id="D", target_handles=("A",), anchor=LineAnchor.CENTER, target_length=20),
        (line("A"),),
    )
    assert plan.endpoints["A"] == (Point3D(x=-5, y=0, z=0), Point3D(x=15, y=0, z=0))


def test_jl_requires_explicit_order_and_tolerance() -> None:
    snapshots = (line("A", end=Point3D(x=1, y=0)), line("B", start=Point3D(x=1, y=0), end=Point3D(x=2, y=0)))
    plan = plan_join_line(
        JoinLineRequest(
            document_id="D", ordered_handles=("A", "B"), tolerance=0.01, target_layer="J", delete_sources=True
        ),
        snapshots,
    )
    assert plan.vertices == (Point3D(x=0, y=0, z=0), Point3D(x=1, y=0, z=0), Point3D(x=2, y=0, z=0))
    with pytest.raises(ValueError, match="tolerance"):
        plan_join_line(
            JoinLineRequest(
                document_id="D", ordered_handles=("A", "B"), tolerance=0.01, target_layer="J", delete_sources=False
            ),
            (line("A", end=Point3D(x=1, y=0)), line("B", start=Point3D(x=2, y=0), end=Point3D(x=3, y=0))),
        )


def test_mc_creates_equal_displacements() -> None:
    plan = plan_multi_copy(
        MultiCopyRequest(
            document_id="D",
            source_handles=("A",),
            displacement=Point3D(x=2, y=0),
            copy_count=3,
            include_original_position=False,
        )
    )
    assert [item.translation.x for item in plan.transforms] == [2, 4, 6]


def test_mlc_requires_supplied_style_components() -> None:
    with pytest.raises(ValueError, match="unrecovered"):
        MlineConvertRequest(
            document_id="D",
            target_handles=("M",),
            wall_layer="W",
            delete_sources=True,
            require_supplied_components=False,
        )
    snapshot = MlineSnapshot(
        handle="M",
        component_lines=((Point3D(x=0, y=0), Point3D(x=1, y=0)), (Point3D(x=0, y=1), Point3D(x=1, y=1))),
        source_style="WALL",
    )
    plan = plan_mline_convert(
        MlineConvertRequest(document_id="D", target_handles=("M",), wall_layer="W", delete_sources=True), (snapshot,)
    )
    assert len(plan.component_lines["M"]) == 2


def test_non_dry_requires_approval_fingerprint() -> None:
    with pytest.raises(ValueError, match="approval fingerprint"):
        ExtendLineRequest(
            document_id="D", target_handles=("A",), anchor=LineAnchor.START, target_length=20, dry_run=False
        )


def test_registers_six_read_only_tools() -> None:
    mcp = FastMCP("batch21a-test")
    register_headless_core_batch21a_tools(mcp)
    tools = asyncio.run(mcp.list_tools())
    assert len(tools) == 6
    assert all(tool.annotations and tool.annotations.readOnlyHint for tool in tools)
