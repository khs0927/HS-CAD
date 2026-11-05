import asyncio

import pytest
from mcp.server.fastmcp import FastMCP

from xicad_mcp.headless_core_batch1 import Point3D
from xicad_mcp.headless_core_batch14 import GeometrySnapshot
from xicad_mcp.headless_core_batch16 import (
    BarPlacement,
    BlockPatternRequest,
    CalendarRequest,
    CenterMode,
    CenterPolylineRequest,
    ColumnKind,
    ColumnRequest,
    ConcreteShape,
    CurtainType,
    CurtainWallRequest,
    DoorLeafDivision,
    DoorRequest,
    DoorSwing,
    DoorVariant,
    EscalatorElevationRequest,
    EscalatorStyle,
    ExplodedViewRequest,
    PatternElement,
    ScheduleRequest,
    SwingDisplay,
    TableCell,
    plan_beam_schedule,
    plan_block_pattern,
    plan_calendar,
    plan_center_polyline,
    plan_column,
    plan_column_schedule,
    plan_curtain_wall,
    plan_door,
    plan_escalator_elevation,
    plan_exploded_view,
    register_headless_core_batch16_tools,
)


def schedule() -> ScheduleRequest:
    return ScheduleRequest(
        document_id="D",
        insertion_point=Point3D(x=0, y=0),
        rows=2,
        columns=2,
        row_height=5,
        column_widths=(10, 20),
        cells=(TableCell(row=0, column=0, text="MARK"),),
        grid_layer="GRID",
        text_layer="TEXT",
        text_height=2.5,
    )


def test_bli_and_cli_have_distinct_aliases() -> None:
    assert plan_beam_schedule(schedule()).command_alias == "BLI"
    assert plan_column_schedule(schedule()).command_alias == "CLI"
    assert len(plan_beam_schedule(schedule()).horizontal_lines) == 3


def test_bpt_definition_only() -> None:
    request = BlockPatternRequest(
        document_id="D",
        pattern_name="BRICK_1",
        base_point=Point3D(x=0, y=0),
        elements=(PatternElement(block_name="B", offset=Point3D(x=1, y=2), rotation_degrees=0, scale=1),),
    )
    assert plan_block_pattern(request).external_write_blocked
    with pytest.raises(ValueError, match="installation"):
        request.model_copy(update={"output_definition_only": False}).model_validate(
            request.model_copy(update={"output_definition_only": False}).model_dump()
        )


def test_calendar_is_deterministic() -> None:
    plan = plan_calendar(
        CalendarRequest(
            document_id="D",
            year=2026,
            month=7,
            week_start=0,
            insertion_point=Point3D(x=0, y=0),
            cell_width=10,
            cell_height=8,
            layer="C",
            text_style="Standard",
        )
    )
    assert plan.title == "July 2026"
    assert 21 in plan.weeks[3]


def test_cep_interpolates_center() -> None:
    snapshots = (
        GeometrySnapshot(
            handle="A",
            entity_type="LWPOLYLINE",
            vertices=(Point3D(x=0, y=0), Point3D(x=2, y=0)),
            layer="A",
        ),
        GeometrySnapshot(
            handle="B",
            entity_type="LWPOLYLINE",
            vertices=(Point3D(x=0, y=2), Point3D(x=2, y=2)),
            layer="B",
        ),
    )
    plan = plan_center_polyline(
        CenterPolylineRequest(
            document_id="D",
            first_handle="A",
            second_handle="B",
            mode=CenterMode.CENTER,
            node_count=2,
            divisions=2,
            layer="CENTER",
        ),
        snapshots,
    )
    assert plan.output_lines[0][0] == Point3D(x=0, y=1, z=0)


def test_col_requires_steel_dimensions_for_src() -> None:
    with pytest.raises(ValueError, match="steel dimensions"):
        ColumnRequest(
            document_id="D",
            insertion_points=(Point3D(x=0, y=0),),
            kind=ColumnKind.SRC,
            concrete_shape=ConcreteShape.RECTANGLE,
            concrete_width=500,
            concrete_depth=500,
            concrete_layer="C",
            steel_layer="S",
        )


def test_col_outputs_eccentric_center() -> None:
    plan = plan_column(
        ColumnRequest(
            document_id="D",
            insertion_points=(Point3D(x=0, y=0),),
            kind=ColumnKind.RC,
            concrete_shape=ConcreteShape.CIRCLE,
            concrete_width=500,
            concrete_depth=500,
            eccentric_x=10,
            eccentric_y=-5,
            concrete_layer="C",
            steel_layer="S",
        )
    )
    assert plan.creates[0].center == Point3D(x=10, y=-5, z=0)


def test_cw_recovers_division_and_cap_settings() -> None:
    plan = plan_curtain_wall(
        CurtainWallRequest(
            document_id="D",
            baseline=(Point3D(x=0, y=0), Point3D(x=10, y=0)),
            kind=CurtainType.CURTAIN_WALL,
            divisions=4,
            bar_width=1,
            bar_depth=2,
            cap_enabled=True,
            cap_width=3,
            cap_depth=2,
            placement=BarPlacement.CENTER,
            glass_thickness=0.02,
            glass_layer="GLASS",
            bar_layer="BAR",
            elevation_layer="ELEV",
            straighten_curves=True,
            group_output=True,
        )
    )
    assert plan.division_fractions == (0.25, 0.5, 0.75)


def door(variant: DoorVariant) -> DoorRequest:
    return DoorRequest(
        document_id="D",
        variant=variant,
        hinge_point=Point3D(x=0, y=0),
        opening_end_point=Point3D(x=900, y=0),
        wall_depth=200,
        offset=0,
        swing=DoorSwing.ONE_WAY,
        leaf_division=DoorLeafDivision.TWO_TO_ONE,
        opening_angle_degrees=90,
        frame_width=50,
        leaf_thickness=40,
        threshold_depth=0,
        swing_display=SwingDisplay.ARC,
        frame_layer="FRAME",
        swing_layer="SWING",
        elevation_layer="ELEV",
        group_output=True,
    )


@pytest.mark.parametrize("variant", list(DoorVariant))
def test_d1_d2_d3_are_explicit_variants(variant: DoorVariant) -> None:
    plan = plan_door(door(variant))
    assert plan.command_alias == variant.value.upper()
    assert plan.leaf_ratios == pytest.approx((2 / 3, 1 / 3))


def test_dev_requires_border_direction() -> None:
    with pytest.raises(ValueError, match="at least one"):
        ExplodedViewRequest(
            document_id="D",
            station_points=(Point3D(x=0, y=0), Point3D(x=1, y=0)),
            base_height=0,
            draw_horizontal=False,
            draw_vertical=False,
            border_layer="B",
            separator_layer="S",
        )
    plan = plan_exploded_view(
        ExplodedViewRequest(
            document_id="D",
            station_points=(Point3D(x=0, y=0), Point3D(x=1, y=0)),
            base_height=3,
            draw_horizontal=True,
            draw_vertical=True,
            border_layer="B",
            separator_layer="S",
        )
    )
    assert len(plan.vertical_points) == 2


def test_eed_accepts_only_dcl_angles() -> None:
    with pytest.raises(ValueError, match="30 or 35"):
        EscalatorElevationRequest(
            document_id="D",
            insertion_point=Point3D(x=0, y=0),
            style=EscalatorStyle.STYLE1,
            floors=2,
            floor_height=3500,
            angle_degrees=32,
            layer="E",
        )
    plan = plan_escalator_elevation(
        EscalatorElevationRequest(
            document_id="D",
            insertion_point=Point3D(x=0, y=0),
            style=EscalatorStyle.STYLE1,
            floors=2,
            floor_height=3500,
            angle_degrees=35,
            layer="E",
        )
    )
    assert plan.rise == 7000


def test_non_dry_requires_approval_fingerprint() -> None:
    with pytest.raises(ValueError, match="approval fingerprint"):
        CalendarRequest(
            document_id="D",
            year=2026,
            month=7,
            week_start=0,
            insertion_point=Point3D(x=0, y=0),
            cell_width=10,
            cell_height=8,
            layer="C",
            text_style="S",
            dry_run=False,
        )


def test_registers_12_read_only_tools() -> None:
    mcp = FastMCP("batch16-test")
    register_headless_core_batch16_tools(mcp)
    tools = asyncio.run(mcp.list_tools())
    assert len(tools) == 12
    assert all(tool.annotations and tool.annotations.readOnlyHint for tool in tools)
