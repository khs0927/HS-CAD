import asyncio

import pytest
from mcp.server.fastmcp import FastMCP

from xicad_mcp.headless_core_batch1 import Point3D
from xicad_mcp.headless_core_batch14 import GeometrySnapshot
from xicad_mcp.headless_core_batch17 import (
    ConnectionKind,
    ElevatorRequest,
    EscalatorPlanRequest,
    HatchBoundaryRequest,
    HatchPointRequest,
    HatchSnapshot,
    HeatGridRequest,
    InsulationMode,
    InsulationRequest,
    ParkingRequest,
    PartialZoomMode,
    PartialZoomRequest,
    QRCodeRequest,
    ScaleBarRequest,
    StairRequest,
    StairView,
    SteelBeamMode,
    SteelBeamRequest,
    plan_elevator,
    plan_escalator_plan,
    plan_hatch_boundary,
    plan_hatch_point,
    plan_heat_grid,
    plan_insulation,
    plan_parking,
    plan_partial_zoom,
    plan_qr_code,
    plan_scale_bar,
    plan_stair,
    plan_steel_beam,
    register_headless_core_batch17_tools,
)


def test_elv_validates_cars_inside_shaft() -> None:
    plan = plan_elevator(
        ElevatorRequest(
            document_id="D",
            center=Point3D(x=0, y=0),
            shaft_width=5000,
            shaft_depth=2500,
            car_width=2000,
            car_depth=2000,
            door_width=1000,
            car_count=2,
            shaft_layer="S",
            car_layer="C",
        )
    )
    assert len(plan.cars) == 2
    with pytest.raises(ValueError, match="fit"):
        ElevatorRequest(
            document_id="D",
            center=Point3D(x=0, y=0),
            shaft_width=3000,
            shaft_depth=2500,
            car_width=2000,
            car_depth=2000,
            door_width=1000,
            car_count=2,
            shaft_layer="S",
            car_layer="C",
        )


def test_epd_explicit_run_and_widths() -> None:
    plan = plan_escalator_plan(
        EscalatorPlanRequest(
            document_id="D",
            start=Point3D(x=0, y=0),
            end=Point3D(x=10, y=0),
            overall_width=2,
            tread_width=1.2,
            step_pitch=0.4,
            balustrade_width=0.2,
            layer="E",
        )
    )
    assert plan.centerline[1].x == 10


def hatch() -> HatchSnapshot:
    return HatchSnapshot(
        handle="H",
        loops=((Point3D(x=0, y=0), Point3D(x=1, y=0), Point3D(x=1, y=1)),),
        origin=Point3D(x=0, y=0),
        layer="H",
    )


def test_hb_recreates_snapshot_loops() -> None:
    plan = plan_hatch_boundary(
        HatchBoundaryRequest(document_id="D", hatch_handles=("H",), target_layer="B"), (hatch(),)
    )
    assert len(plan.boundaries["H"][0]) == 3


def test_hgrid_generates_serpentine_path() -> None:
    plan = plan_heat_grid(
        HeatGridRequest(
            document_id="D", lower_left=Point3D(x=0, y=0), width=10, height=6, spacing=2, edge_offset=1, layer="P"
        )
    )
    assert len(plan.path) == 6
    assert plan.path[0].x < plan.path[1].x and plan.path[2].x > plan.path[3].x


def test_hp_changes_origin_only_on_editable_hatch() -> None:
    plan = plan_hatch_point(
        HatchPointRequest(document_id="D", hatch_handles=("H",), new_origin=Point3D(x=5, y=5)), (hatch(),)
    )
    assert plan.origin_changes["H"].x == 5


def test_ins_recovers_dcl_density_thresholds() -> None:
    plan = plan_insulation(
        InsulationRequest(
            document_id="D",
            baseline=(Point3D(x=0, y=0), Point3D(x=5, y=0)),
            thickness=120,
            mode=InsulationMode.COMBINED,
            small_threshold=50,
            medium_threshold=150,
            cut_to_length=True,
            remove_end_piece=True,
            layer="I",
        )
    )
    assert plan.density_class == "medium"


def test_pk_restricts_angle_policy() -> None:
    with pytest.raises(ValueError, match="angle"):
        ParkingRequest(
            document_id="D",
            origin=Point3D(x=0, y=0),
            stall_count=2,
            stall_width=2.5,
            stall_depth=5,
            aisle_width=6,
            angle_degrees=22,
            layer="P",
        )
    assert (
        len(
            plan_parking(
                ParkingRequest(
                    document_id="D",
                    origin=Point3D(x=0, y=0),
                    stall_count=2,
                    stall_width=2.5,
                    stall_depth=5,
                    aisle_width=6,
                    angle_degrees=90,
                    layer="P",
                )
            ).stalls
        )
        == 2
    )


def test_pz_applies_scale_and_translation() -> None:
    snapshot = GeometrySnapshot(
        handle="A", entity_type="LINE", vertices=(Point3D(x=1, y=1), Point3D(x=2, y=1)), layer="L"
    )
    request = PartialZoomRequest(
        document_id="D",
        source_handles=("A",),
        mode=PartialZoomMode.RECTANGLE,
        source_center=Point3D(x=1, y=1),
        target_center=Point3D(x=10, y=10),
        zoom_factor=2,
        boundary_points=(Point3D(x=0, y=0), Point3D(x=3, y=3)),
        layer="Z",
        color=1,
        linetype="Continuous",
        create_block=True,
    )
    assert plan_partial_zoom(request, (snapshot,)).transformed_vertices["A"][1] == Point3D(x=12, y=10, z=0)


def test_qrc_requires_digest_bound_square_matrix() -> None:
    modules = tuple(tuple(row == column for column in range(21)) for row in range(21))
    plan = plan_qr_code(
        QRCodeRequest(
            document_id="D",
            payload="https://example.com",
            payload_digest="sha256:" + "a" * 64,
            modules=modules,
            insertion_point=Point3D(x=0, y=0),
            module_size=1,
            layer="QR",
        )
    )
    assert len(plan.dark_cells) == 21


def test_scb_creates_ticks_and_labels() -> None:
    plan = plan_scale_bar(
        ScaleBarRequest(
            document_id="D",
            origin=Point3D(x=0, y=0),
            drawing_scale=100,
            segment_length=1000,
            segment_count=3,
            units_label="m",
            layer="S",
            text_height=2.5,
        )
    )
    assert len(plan.tick_points) == 4 and plan.labels[-1] == "30 m"


def test_stb_recovers_dcl_beam_mark() -> None:
    plan = plan_steel_beam(
        SteelBeamRequest(
            document_id="D",
            start=Point3D(x=0, y=0),
            end=Point3D(x=5, y=0),
            mode=SteelBeamMode.STRUCTURAL_SYMBOL,
            offset=0,
            beam_width=300,
            web_thickness=8,
            web_linetype="HIDDEN",
            prefix="g",
            beam_number=1,
            uppercase=True,
            head_connection=ConnectionKind.RIGID,
            tail_connection=ConnectionKind.PIN,
            head_size=2,
            line_thickness=0.3,
            text_size=2.5,
            symbol_layer="S",
            text_layer="T",
        )
    )
    assert plan.beam_mark == "G1"


def test_stc_computes_tread_and_riser() -> None:
    plan = plan_stair(
        StairRequest(
            document_id="D",
            origin=Point3D(x=0, y=0),
            view=StairView.ELEVATION,
            total_rise=3000,
            total_run=4500,
            step_count=15,
            round_tread_to_ten=True,
            slab_type=1,
            riser_depth=150,
            slab_thickness=200,
            top_finish_thickness=20,
            bottom_finish_thickness=10,
            elevation_layer="E",
            section_layer="S",
            handrail_layer="H",
            finish_layer="F",
            number_layer="N",
        )
    )
    assert plan.tread == 300 and plan.riser == 200


def test_live_requires_approval_fingerprint() -> None:
    with pytest.raises(ValueError, match="approval fingerprint"):
        ScaleBarRequest(
            document_id="D",
            origin=Point3D(x=0, y=0),
            drawing_scale=100,
            segment_length=1000,
            segment_count=3,
            units_label="m",
            layer="S",
            text_height=2.5,
            dry_run=False,
        )


def test_registers_12_read_only_tools() -> None:
    mcp = FastMCP("batch17-test")
    register_headless_core_batch17_tools(mcp)
    tools = asyncio.run(mcp.list_tools())
    assert len(tools) == 12
    assert all(tool.annotations and tool.annotations.readOnlyHint for tool in tools)
