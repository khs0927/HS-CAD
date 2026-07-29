from __future__ import annotations

from typing import Any

import pytest

from xicad_mcp import live_batch18 as live
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
)


class Layer:
    def __init__(self, name: str) -> None:
        self.Name, self.Color, self.Linetype, self.Lock = name, 7, "Continuous", False


class Layers:
    def __init__(self) -> None:
        self.layers = {name: Layer(name) for name in ("C", "W", "Z")}

    def Item(self, name: str) -> Layer:
        return self.layers[name]


class Line:
    ObjectName = "AcDbLine"

    def __init__(self, handle: str, start: Any, end: Any) -> None:
        self.Handle, self.StartPoint, self.EndPoint = handle, start, end
        self.Layer = "0"


class Polyline:
    ObjectName = "AcDbPolyline"

    def __init__(self, handle: str, coordinates: list[float]) -> None:
        self.Handle, self.Coordinates = handle, coordinates
        self.Elevation, self.Layer, self.Closed = 0.0, "0", False


class Space:
    def __init__(self, doc: Doc) -> None:
        self.doc = doc

    def AddLine(self, start: Any, end: Any) -> Line:
        item = Line(f"N{len(self.doc.entities)}", start, end)
        self.doc.entities.append(item)
        return item

    def AddLightWeightPolyline(self, coordinates: list[float]) -> Polyline:
        item = Polyline(f"N{len(self.doc.entities)}", list(coordinates))
        self.doc.entities.append(item)
        return item


class Doc:
    Name = "Drawing1.dwg"

    def __init__(self) -> None:
        self.Layers = Layers()
        self.entities: list[Any] = []
        self.ModelSpace = Space(self)
        self.marks: list[str] = []

    def StartUndoMark(self) -> None:
        self.marks.append("start")

    def EndUndoMark(self) -> None:
        self.marks.append("end")


@pytest.fixture
def doc(monkeypatch: pytest.MonkeyPatch) -> Doc:
    drawing = Doc()
    monkeypatch.setattr(live, "_drawing", lambda _name: drawing)
    monkeypatch.setattr(live, "_entities", lambda _doc: {item.Handle.casefold(): item for item in drawing.entities})
    monkeypatch.setattr(live, "_variant", lambda point: (point.x, point.y, point.z))
    monkeypatch.setattr(
        live,
        "_coordinates",
        lambda points: [coordinate for point in points for coordinate in (point.x, point.y)],
    )
    return drawing


def truss() -> TrussRequest:
    return TrussRequest(
        document_id="Drawing1.dwg",
        start=Point3D(x=0, y=0),
        end=Point3D(x=10, y=0),
        depth=2,
        panel_count=4,
        diagonal_starts_up=True,
        chord_layer="C",
        web_layer="W",
    )


def test_truss_preview_execute_and_postconditions(doc: Doc) -> None:
    request = truss()
    preview = live.preview_live_truss(request)
    wrapped = live.LiveTrussExecuteRequest(
        request=request,
        expected_chord_layer=live.LiveLayerEvidence.model_validate(preview["expected_chord_layer"]),
        expected_web_layer=live.LiveLayerEvidence.model_validate(preview["expected_web_layer"]),
        approval_fingerprint=preview["approval_fingerprint"],
    )
    result = live.execute_live_truss(wrapped)
    assert preview["create_count"] == 6
    assert len(result.created_handles) == 6
    assert [item.Layer for item in doc.entities] == ["C", "C", "W", "W", "W", "W"]
    assert doc.marks == ["start", "end"]


def test_truss_rejects_stale_layer(doc: Doc) -> None:
    request = truss()
    preview = live.preview_live_truss(request)
    wrapped = live.LiveTrussExecuteRequest(
        request=request,
        expected_chord_layer=live.LiveLayerEvidence.model_validate(preview["expected_chord_layer"]),
        expected_web_layer=live.LiveLayerEvidence.model_validate(preview["expected_web_layer"]),
        approval_fingerprint=preview["approval_fingerprint"],
    )
    doc.Layers.layers["C"].Color = 3
    with pytest.raises(ValueError, match="no longer matches"):
        live.execute_live_truss(wrapped)


def zigzag() -> ZigZagRequest:
    return ZigZagRequest(
        document_id="Drawing1.dwg",
        start=Point3D(x=0, y=0),
        end=Point3D(x=10, y=0),
        amplitude=1,
        pitch=2,
        start_positive=True,
        layer="Z",
    )


def test_zigzag_preview_execute_exact_polyline(doc: Doc) -> None:
    request = zigzag()
    preview = live.preview_live_zigzag(request)
    result = live.execute_live_zigzag(
        live.LiveZigZagExecuteRequest(
            request=request,
            expected_layer=live.LiveLayerEvidence.model_validate(preview["expected_layer"]),
            approval_fingerprint=preview["approval_fingerprint"],
        )
    )
    assert result.created_handles == ("N0",)
    assert doc.entities[0].Coordinates == [0, 0, 2, 1, 4, -1, 6, 1, 8, -1, 10, 0]


def test_zigzag_blocks_nonplanar_lwpolyline(doc: Doc) -> None:
    request = zigzag().model_copy(update={"end": Point3D(x=10, y=0, z=5)})
    with pytest.raises(ValueError, match="one elevation"):
        live.preview_live_zigzag(request)


def table() -> CadTableSnapshot:
    return CadTableSnapshot(handle="T", cells=(("A", "LONG"),), column_widths=(10, 10), text_height=2)


def hatch() -> HatchSnapshot:
    return HatchSnapshot(
        handle="H",
        loops=((Point3D(x=0, y=0), Point3D(x=1, y=0), Point3D(x=1, y=1)),),
        origin=Point3D(x=0, y=0),
        layer="H",
    )


def test_table_excel_and_hatch_operations_are_read_only_blocked_previews() -> None:
    taj = live.preview_live_taj(
        TableWidthRequest(
            document_id="D",
            table_handles=("T",),
            character_width_factor=0.6,
            horizontal_padding=1,
            minimum_width=2,
        ),
        (table(),),
    )
    c2e = live.preview_live_c2e(
        CadToExcelRequest(
            document_id="D",
            table_handle="T",
            transfer_format=TableTransferFormat.MATRIX,
            include_geometry=True,
        ),
        (table(),),
    )
    e2c = live.preview_live_e2c(
        ExcelToCadRequest(
            document_id="D",
            cells=(("A",),),
            column_widths=(10,),
            row_heights=(5,),
            insertion_point=Point3D(x=0, y=0),
            grid_layer="G",
            text_layer="T",
            source_digest="sha256:" + "a" * 64,
        )
    )
    hc = live.preview_live_hc(
        HatchCloneRequest(
            document_id="D",
            source_handle="H",
            targets=(HatchCloneTarget(insertion_point=Point3D(x=1, y=1), scale=1),),
        ),
        (hatch(),),
    )
    he = live.preview_live_hex(
        HatchExportRequest(document_id="D", hatch_handles=("H",), include_boundaries=True),
        (hatch(),),
    )
    for preview in (taj, c2e, e2c, hc, he):
        assert not preview["mutation"] and not preview["live_executable"]
        assert preview["approval_fingerprint"].startswith("sha256:")


def test_incomplete_architectural_geometry_is_blocked_with_plan_visible() -> None:
    stp = StairPlanRequest(
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
    window = WindowRequest(
        document_id="D",
        variant=WindowVariant.W3,
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
    opening = WallOpeningRequest(
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
    for preview in (
        live.preview_live_stp(stp),
        live.preview_live_window(window),
        live.preview_live_wo(opening),
    ):
        assert preview["plan"] and not preview["live_executable"]
    assert "disagree" in live.preview_live_window(window)["blocked_reason"]


def test_registers_thirteen_tools_with_two_executors() -> None:
    class MCP:
        def __init__(self) -> None:
            self.names: list[str] = []

        def tool(self, *, name: str, annotations: Any) -> Any:
            del annotations
            self.names.append(name)
            return lambda function: function

    mcp = MCP()
    live.register_live_batch18_tools(mcp)  # type: ignore[arg-type]
    assert len(mcp.names) == 13
    assert [name for name in mcp.names if "execute" in name] == [
        "xicad_execute_live_truss",
        "xicad_execute_live_zigzag",
    ]
