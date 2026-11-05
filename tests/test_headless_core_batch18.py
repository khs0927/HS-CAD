import asyncio

import pytest
from mcp.server.fastmcp import FastMCP

from xicad_mcp.headless_core_batch1 import Point3D
from xicad_mcp.headless_core_batch17 import HatchSnapshot
from xicad_mcp.headless_core_batch18 import (
    CadTableSnapshot,
    CadToExcelRequest,
    ExcelToCadRequest,
    HatchCloneRequest,
    HatchCloneTarget,
    HatchExportRequest,
    StairDirection,
    StairPlanKind,
    StairPlanRequest,
    TableTransferFormat,
    TableWidthRequest,
    TrussRequest,
    WallCleanup,
    WallOpeningRequest,
    WindowDetail,
    WindowGlazing,
    WindowRequest,
    WindowVariant,
    ZigZagRequest,
    plan_cad_to_excel,
    plan_excel_to_cad,
    plan_hatch_clone,
    plan_hatch_export,
    plan_stair_plan,
    plan_table_width,
    plan_truss,
    plan_wall_opening,
    plan_window,
    plan_zigzag,
    register_headless_core_batch18_tools,
)


def table() -> CadTableSnapshot:
    return CadTableSnapshot(handle="T", cells=(("A", "LONG"), ("B", "X")), column_widths=(10, 10), text_height=2)


def hatch() -> HatchSnapshot:
    return HatchSnapshot(
        handle="H",
        loops=((Point3D(x=0, y=0), Point3D(x=1, y=0), Point3D(x=1, y=1)),),
        origin=Point3D(x=0, y=0),
        layer="H",
    )


def test_stp_recovers_dcl_tread_geometry() -> None:
    plan = plan_stair_plan(
        StairPlanRequest(
            document_id="D",
            origin=Point3D(x=0, y=0),
            kind=StairPlanKind.STRAIGHT,
            direction=StairDirection.UP,
            flight_width=1200,
            start_gap=100,
            step_count=10,
            tread_depth=300,
            flight_gap=100,
            landing_width=1200,
            handrail_enabled=True,
            handrail_width=50,
            arrow_enabled=True,
            cut_line_enabled=True,
            anti_slip_enabled=False,
            stair_layer="S",
            handrail_layer="H",
            symbol_layer="Y",
            text_layer="T",
            number_layer="N",
        )
    )
    assert len(plan.tread_lines) == 11


def test_taj_uses_explicit_text_metric() -> None:
    plan = plan_table_width(
        TableWidthRequest(
            document_id="D", table_handles=("T",), character_width_factor=0.6, horizontal_padding=1, minimum_width=2
        ),
        (table(),),
    )
    assert plan.widths_by_handle["T"] == pytest.approx((3.2, 6.8))


def test_truss_is_deterministic() -> None:
    plan = plan_truss(
        TrussRequest(
            document_id="D",
            start=Point3D(x=0, y=0),
            end=Point3D(x=10, y=0),
            depth=2,
            panel_count=4,
            diagonal_starts_up=True,
            chord_layer="C",
            web_layer="W",
        )
    )
    assert len(plan.webs) == 4 and plan.upper_chord[0].y == 2


def window(variant: WindowVariant) -> WindowRequest:
    return WindowRequest(
        document_id="D",
        variant=variant,
        start=Point3D(x=0, y=0),
        end=Point3D(x=1200, y=0),
        wall_depth=200,
        divisions=2,
        glazing=WindowGlazing.DOUBLE,
        detail=WindowDetail.DETAIL,
        reverse_frame=False,
        frame_depth=100,
        frame_width=40,
        glass_thickness=12,
        wall_gap=10,
        frame_layer="F",
        elevation_layer="E",
        glass_layer="G",
        center_layer="C",
        group_output=True,
    )


@pytest.mark.parametrize("variant", list(WindowVariant))
def test_window_variants_are_explicit(variant: WindowVariant) -> None:
    assert plan_window(window(variant)).command_alias == variant.value.upper()


def test_wo_preserves_dcl_settings() -> None:
    request = WallOpeningRequest(
        document_id="D",
        start=Point3D(x=0, y=0),
        end=Point3D(x=1, y=0),
        centered=True,
        offset=0,
        external_projection=10,
        internal_projection=20,
        omit_elevation_line=True,
        cleanup=WallCleanup.EACH_WALL,
        elevation_layer="E",
    )
    assert plan_wall_opening(request).request_spec.internal_projection == 20


def test_zigzag_generates_endpoints() -> None:
    request = ZigZagRequest(
        document_id="D",
        start=Point3D(x=0, y=0),
        end=Point3D(x=10, y=0),
        amplitude=1,
        pitch=2,
        start_positive=True,
        layer="Z",
    )
    plan = plan_zigzag(request)
    assert plan.vertices[0] == request.start and plan.vertices[-1] == request.end


def test_c2e_returns_data_without_excel_automation() -> None:
    plan = plan_cad_to_excel(
        CadToExcelRequest(
            document_id="D", table_handle="T", transfer_format=TableTransferFormat.MATRIX, include_geometry=True
        ),
        (table(),),
    )
    assert plan.external_excel_blocked and plan.cells[0][1] == "LONG"


def test_e2c_requires_digest_bound_rectangular_matrix() -> None:
    plan = plan_excel_to_cad(
        ExcelToCadRequest(
            document_id="D",
            cells=(("A", "B"),),
            column_widths=(10, 10),
            row_heights=(5,),
            insertion_point=Point3D(x=0, y=0),
            grid_layer="G",
            text_layer="T",
            source_digest="sha256:" + "a" * 64,
        )
    )
    assert plan.external_excel_blocked


def test_hc_blocks_unsupported_associativity() -> None:
    with pytest.raises(ValueError, match="associativity"):
        HatchCloneRequest(
            document_id="D",
            source_handle="H",
            targets=(HatchCloneTarget(insertion_point=Point3D(x=1, y=1), scale=1),),
            preserve_associativity=True,
        )
    plan = plan_hatch_clone(
        HatchCloneRequest(
            document_id="D", source_handle="H", targets=(HatchCloneTarget(insertion_point=Point3D(x=1, y=1), scale=1),)
        ),
        (hatch(),),
    )
    assert plan.source.handle == "H"


def test_hex_blocks_file_write() -> None:
    with pytest.raises(ValueError, match="file write"):
        HatchExportRequest(document_id="D", hatch_handles=("H",), include_boundaries=True, output_definition_only=False)
    assert plan_hatch_export(
        HatchExportRequest(document_id="D", hatch_handles=("H",), include_boundaries=True), (hatch(),)
    ).external_write_blocked


def test_live_requires_approval_fingerprint() -> None:
    with pytest.raises(ValueError, match="approval fingerprint"):
        TableWidthRequest(
            document_id="D",
            table_handles=("T",),
            character_width_factor=0.6,
            horizontal_padding=1,
            minimum_width=2,
            dry_run=False,
        )


def test_registers_12_read_only_tools() -> None:
    mcp = FastMCP("batch18-test")
    register_headless_core_batch18_tools(mcp)
    tools = asyncio.run(mcp.list_tools())
    assert len(tools) == 12
    assert all(tool.annotations and tool.annotations.readOnlyHint for tool in tools)
