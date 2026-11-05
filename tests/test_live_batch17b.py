from __future__ import annotations

from typing import Any

from xicad_mcp import live_batch17b as live
from xicad_mcp.headless_core_batch1 import Point3D
from xicad_mcp.headless_core_batch14 import GeometrySnapshot
from xicad_mcp.headless_core_batch17 import (
    ConnectionKind,
    ParkingRequest,
    PartialZoomMode,
    PartialZoomRequest,
    QRCodeRequest,
    ScaleBarRequest,
    StairRequest,
    StairView,
    SteelBeamMode,
    SteelBeamRequest,
)


def test_pk_is_fingerprinted_preview_only_with_semantic_gap() -> None:
    request = ParkingRequest(
        document_id="D",
        origin=Point3D(x=0, y=0),
        stall_count=2,
        stall_width=2500,
        stall_depth=5000,
        aisle_width=6000,
        angle_degrees=90,
        layer="P",
    )
    preview = live.preview_live_pk(request)
    assert preview["plan"]["stalls"]
    assert not preview["mutation"] and not preview["live_executable"]
    assert "aisle" in preview["blocked_reason"]
    assert preview["approval_fingerprint"].startswith("sha256:")


def test_pz_preview_includes_exact_supplied_source_but_blocks_incomplete_output() -> None:
    request = PartialZoomRequest(
        document_id="D",
        source_handles=("A",),
        mode=PartialZoomMode.RECTANGLE,
        source_center=Point3D(x=0, y=0),
        target_center=Point3D(x=100, y=100),
        zoom_factor=2,
        boundary_points=(Point3D(x=0, y=0), Point3D(x=10, y=10)),
        layer="Z",
        color=1,
        linetype="Continuous",
        create_block=False,
    )
    snapshot = GeometrySnapshot(
        handle="A",
        entity_type="LINE",
        vertices=(Point3D(x=0, y=0), Point3D(x=10, y=0)),
        layer="0",
    )
    preview = live.preview_live_pz(request, (snapshot,))
    assert preview["expected_sources"][0]["handle"] == "A"
    assert preview["plan"]["transformed_vertices"]["A"][1]["x"] == 120
    assert "boundary rendering" in preview["blocked_reason"]


def test_qrc_reports_payload_digest_mismatch_without_drawing() -> None:
    modules = tuple(tuple(row == column for column in range(21)) for row in range(21))
    request = QRCodeRequest(
        document_id="D",
        payload="payload",
        payload_digest="sha256:" + "a" * 64,
        modules=modules,
        insertion_point=Point3D(x=0, y=0),
        module_size=1,
        layer="QR",
    )
    preview = live.preview_live_qrc(request)
    assert not preview["payload_digest_matches"]
    assert len(preview["plan"]["dark_cells"]) == 21
    assert not preview["live_executable"]


def test_scb_stb_stc_plans_are_visible_but_non_executable() -> None:
    scb = ScaleBarRequest(
        document_id="D",
        origin=Point3D(x=0, y=0),
        drawing_scale=100,
        segment_length=1000,
        segment_count=2,
        units_label="m",
        layer="S",
        text_height=2.5,
    )
    stb = SteelBeamRequest(
        document_id="D",
        start=Point3D(x=0, y=0),
        end=Point3D(x=10, y=0),
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
    stc = StairRequest(
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
    for preview in (
        live.preview_live_scb(scb),
        live.preview_live_stb(stb),
        live.preview_live_stc(stc),
    ):
        assert preview["plan"] and preview["source_evidence"]
        assert not preview["mutation"] and not preview["live_executable"]


def test_registers_six_read_only_previews_and_no_executor() -> None:
    class MCP:
        def __init__(self) -> None:
            self.names: list[str] = []

        def tool(self, *, name: str, annotations: Any) -> Any:
            assert annotations.readOnlyHint
            self.names.append(name)
            return lambda function: function

    mcp = MCP()
    live.register_live_batch17b_tools(mcp)  # type: ignore[arg-type]
    assert len(mcp.names) == 6
    assert all("execute" not in name for name in mcp.names)
