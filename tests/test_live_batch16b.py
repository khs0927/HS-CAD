from __future__ import annotations

from typing import Any

import pytest

from xicad_mcp import live_batch16b as live
from xicad_mcp.headless_core_batch1 import Point3D
from xicad_mcp.headless_core_batch16 import (
    CurtainType,
    CurtainWallRequest,
    DoorLeafDivision,
    DoorRequest,
    DoorSwing,
    DoorVariant,
    EscalatorElevationRequest,
    EscalatorStyle,
    ExplodedViewRequest,
    SwingDisplay,
)


class Layer:
    Name, Color, Linetype, Lock = "G", 7, "Continuous", False


class Layers:
    def Item(self, name: str) -> Layer:
        if name != "G":
            raise KeyError(name)
        return Layer()


class Line:
    Layer = "0"

    def __init__(self, handle: str, start: Any, end: Any) -> None:
        self.Handle, self.StartPoint, self.EndPoint = handle, start, end


class Space:
    def __init__(self, doc: Doc) -> None:
        self.doc = doc

    def AddLine(self, start: Any, end: Any) -> Line:
        line = Line(f"N{len(self.doc.entities)}", start, end)
        self.doc.entities.append(line)
        return line


class Doc:
    Name, Layers = "Drawing1.dwg", Layers()

    def __init__(self) -> None:
        self.entities: list[Line] = []
        self.ModelSpace = Space(self)
        self.marks: list[str] = []

    def StartUndoMark(self) -> None:
        self.marks.append("start")

    def EndUndoMark(self) -> None:
        self.marks.append("end")


@pytest.fixture
def doc(monkeypatch: pytest.MonkeyPatch) -> Doc:
    result = Doc()
    monkeypatch.setattr(live, "_drawing", lambda _name: result)
    monkeypatch.setattr(live, "_variant", lambda point: (point.x, point.y, point.z))
    monkeypatch.setattr(live, "_entities", lambda _doc: {item.Handle.casefold(): item for item in result.entities})
    return result


def eed() -> EscalatorElevationRequest:
    return EscalatorElevationRequest(
        document_id="Drawing1.dwg",
        insertion_point=Point3D(x=0, y=0),
        style=EscalatorStyle.STYLE1,
        floors=2,
        floor_height=3000,
        angle_degrees=30,
        layer="G",
    )


def test_eed_preview_execute_exact_slope(doc: Doc) -> None:
    request = eed()
    preview = live.preview_live_eed(request)
    wrapped = live.LiveEedExecuteRequest(
        request=request,
        expected_layer=live.LiveLayerEvidence.model_validate(preview["expected_layer"]),
        approval_fingerprint=preview["approval_fingerprint"],
    )
    result = live.execute_live_eed(wrapped)
    assert doc.entities[0].EndPoint[1] == 6000
    assert result.postcondition_verified and doc.marks == ["start", "end"]


def test_dev_horizontal_only_executes(doc: Doc) -> None:
    request = ExplodedViewRequest(
        document_id=doc.Name,
        station_points=(Point3D(x=0, y=0), Point3D(x=10, y=0)),
        base_height=0,
        draw_horizontal=True,
        draw_vertical=False,
        border_layer="G",
        separator_layer="G",
    )
    preview = live.preview_live_dev(request)
    result = live.execute_live_dev(
        live.LiveDevExecuteRequest(
            request=request,
            expected_layer=live.LiveLayerEvidence.model_validate(preview["expected_layer"]),
            approval_fingerprint=preview["approval_fingerprint"],
        )
    )
    assert result.created_handles == ("N0",)


def test_stale_layer_and_bad_fingerprint_are_rejected(doc: Doc, monkeypatch: pytest.MonkeyPatch) -> None:
    request = eed()
    preview = live.preview_live_eed(request)
    state = live.LiveLayerEvidence.model_validate(preview["expected_layer"])
    bad = live.LiveEedExecuteRequest(request=request, expected_layer=state, approval_fingerprint="sha256:" + "0" * 64)
    with pytest.raises(ValueError, match="fingerprint"):
        live.execute_live_eed(bad)
    monkeypatch.setattr(live, "_layer", lambda _doc, _name: state.model_copy(update={"color": 3}))
    good = bad.model_copy(update={"approval_fingerprint": preview["approval_fingerprint"]})
    with pytest.raises(ValueError, match="no longer matches"):
        live.execute_live_eed(good)


def test_vertical_dev_and_under_specified_architectural_shapes_are_blocked(doc: Doc) -> None:
    vertical = ExplodedViewRequest(
        document_id=doc.Name,
        station_points=(Point3D(x=0, y=0), Point3D(x=10, y=0)),
        base_height=0,
        draw_horizontal=False,
        draw_vertical=True,
        border_layer="G",
        separator_layer="G",
    )
    with pytest.raises(ValueError, match="second endpoints"):
        live.preview_live_dev(vertical)
    cw = CurtainWallRequest(
        document_id=doc.Name,
        baseline=(Point3D(x=0, y=0), Point3D(x=10, y=0)),
        kind=CurtainType.CURTAIN_WALL,
        divisions=2,
        bar_width=1,
        bar_depth=1,
        cap_enabled=False,
        placement="center",
        glass_thickness=1,
        glass_layer="G",
        bar_layer="G",
        elevation_layer="G",
        straighten_curves=False,
        group_output=False,
    )
    with pytest.raises(ValueError, match="output geometry"):
        live.preview_live_cw(cw)


def test_all_door_variants_blocked_without_frame_leaf_swing_geometry(doc: Doc) -> None:
    for variant in DoorVariant:
        request = DoorRequest(
            document_id=doc.Name,
            variant=variant,
            hinge_point=Point3D(x=0, y=0),
            opening_end_point=Point3D(x=10, y=0),
            wall_depth=2,
            offset=0,
            swing=DoorSwing.ONE_WAY,
            leaf_division=DoorLeafDivision.EQUAL,
            opening_angle_degrees=90,
            frame_width=1,
            leaf_thickness=1,
            threshold_depth=0,
            swing_display=SwingDisplay.ARC,
            frame_layer="G",
            swing_layer="G",
            elevation_layer="G",
            group_output=False,
        )
        with pytest.raises(ValueError, match=f"live {variant.value.upper()}"):
            live.preview_live_door(request)


def test_registers_eight_tools() -> None:
    class MCP:
        def __init__(self) -> None:
            self.names: list[str] = []

        def tool(self, *, name: str, annotations: Any) -> Any:
            del annotations
            self.names.append(name)
            return lambda function: function

    mcp = MCP()
    live.register_live_batch16b_tools(mcp)  # type: ignore[arg-type]
    assert len(mcp.names) == 8
