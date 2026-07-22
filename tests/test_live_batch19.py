from __future__ import annotations

from typing import Any

import pytest

from xicad_mcp import live_batch19 as live
from xicad_mcp.headless_core_batch1 import Point3D
from xicad_mcp.headless_core_batch19a import (
    HatchPatternRequest,
    PatternLine,
    PatternWorkMode,
    TableKind,
    TableMethod,
    TableRequest,
)
from xicad_mcp.headless_core_batch19b import (
    BatPlacementMode,
    BreakAndTextRequest,
    BreakTextStation,
    CircleBreakRequest,
    CircleKeep,
    CurveSample,
    DivideToPolylineRequest,
    SourceDisposition,
    TextAngleMode,
)


class Layer:
    def __init__(self, name: str) -> None:
        self.Name, self.Color, self.Linetype, self.Lock = name, 7, "Continuous", False


class Layers:
    def __init__(self) -> None:
        self.items = {name: Layer(name) for name in ("SRC", "ARC")}

    def Item(self, name: str) -> Layer:
        return self.items[name]


class Circle:
    ObjectName, Color, Linetype = "AcDbCircle", 2, "Continuous"

    def __init__(self, doc: Doc) -> None:
        self.doc = doc
        self.Handle = "C1"
        self.Center = (0.0, 0.0, 0.0)
        self.Radius = 10.0
        self.Layer = "SRC"

    def Delete(self) -> None:
        self.doc.entities.remove(self)


class Arc:
    ObjectName = "AcDbArc"

    def __init__(self, handle: str, center: Any, radius: float, start: float, end: float) -> None:
        self.Handle, self.Center, self.Radius = handle, center, radius
        self.StartAngle, self.EndAngle, self.Layer = start, end, "0"


class Space:
    def __init__(self, doc: Doc) -> None:
        self.doc = doc

    def AddArc(self, center: Any, radius: float, start: float, end: float) -> Arc:
        arc = Arc("A1", center, radius, start, end)
        self.doc.entities.append(arc)
        return arc


class Doc:
    Name = "Drawing1.dwg"

    def __init__(self) -> None:
        self.Layers = Layers()
        self.entities: list[Any] = []
        self.entities.append(Circle(self))
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
    return drawing


def circle_break() -> CircleBreakRequest:
    return CircleBreakRequest(
        document_id="Drawing1.dwg",
        source_handle="C1",
        center=Point3D(x=0, y=0),
        radius=10,
        start_angle_degrees=0,
        end_angle_degrees=90,
        keep=CircleKeep.ARC_START_TO_END,
        target_layer="ARC",
    )


def test_cb_preview_execute_exact_arc_and_source_erase(doc: Doc) -> None:
    request = circle_break()
    preview = live.preview_live_cb(request)
    wrapped = live.LiveCbExecuteRequest(
        request=request,
        expected_circle=live.LiveCircleEvidence.model_validate(preview["expected_circle"]),
        expected_target_layer=live.LiveLayerEvidence.model_validate(preview["expected_target_layer"]),
        approval_fingerprint=preview["approval_fingerprint"],
    )
    result = live.execute_live_cb(wrapped)
    assert result.created_handles == ("A1",) and result.erased_handles == ("C1",)
    assert doc.entities[0].Layer == "ARC"
    assert doc.marks == ["start", "end"]


def test_cb_rejects_request_geometry_mismatch_and_stale_circle(doc: Doc) -> None:
    with pytest.raises(ValueError, match="do not match"):
        live.preview_live_cb(circle_break().model_copy(update={"radius": 11}))
    request = circle_break()
    preview = live.preview_live_cb(request)
    wrapped = live.LiveCbExecuteRequest(
        request=request,
        expected_circle=live.LiveCircleEvidence.model_validate(preview["expected_circle"]),
        expected_target_layer=live.LiveLayerEvidence.model_validate(preview["expected_target_layer"]),
        approval_fingerprint=preview["approval_fingerprint"],
    )
    doc.entities[0].Radius = 9
    with pytest.raises(ValueError, match="no longer matches"):
        live.execute_live_cb(wrapped)


def test_hpm_and_tb_are_fingerprinted_blocked_previews() -> None:
    hpm = live.preview_live_hpm(
        HatchPatternRequest(
            document_id="D",
            mode=PatternWorkMode.DRAW,
            pattern_name="TEST",
            description="test",
            lines=(PatternLine(angle_degrees=0, origin_x=0, origin_y=0, delta_x=1, delta_y=1),),
            cell_origin=Point3D(x=0, y=0),
            for_revit_model=False,
        )
    )
    table = live.preview_live_tb(
        TableRequest(
            document_id="D",
            insertion_point=Point3D(x=0, y=0),
            kind=TableKind.CAD_TABLE,
            method=TableMethod.EXPLICIT_SPACING,
            row_count=1,
            column_count=1,
            row_heights=(5,),
            column_widths=(10,),
            approximate_division=False,
            layer="T",
        )
    )
    for preview in (hpm, table):
        assert not preview["mutation"] and not preview["live_executable"]
        assert preview["plan"] and preview["approval_fingerprint"].startswith("sha256:")


def test_break_text_and_sampled_curve_are_blocked_for_missing_geometry_provenance() -> None:
    bat = live.preview_live_bat(
        BreakAndTextRequest(
            document_id="D",
            placement_mode=BatPlacementMode.POSITION,
            stations=(
                BreakTextStation(
                    source_handle="L",
                    break_center=Point3D(x=5, y=0),
                    text_point=Point3D(x=5, y=1),
                    rotation_degrees=0,
                ),
            ),
            first_at_half_spacing=False,
            break_gap=1,
            angle_mode=TextAngleMode.ZERO,
            text="A",
            text_height=2.5,
            text_layer="T",
        )
    )
    dtp = live.preview_live_dtp(
        DivideToPolylineRequest(
            document_id="D",
            curves=(
                CurveSample(
                    source_handle="S",
                    source_entity_type="SPLINE",
                    sampled_vertices=(Point3D(x=0, y=0), Point3D(x=1, y=1)),
                    layer="0",
                ),
            ),
            max_chord_error=0.1,
            source_disposition=SourceDisposition.PRESERVE,
        )
    )
    assert "parameterization" in bat["blocked_reason"]
    assert "provenance" in dtp["blocked_reason"]
    assert not bat["live_executable"] and not dtp["live_executable"]


def test_all_requested_aliases_have_explicit_decision_and_only_cb_executes() -> None:
    assert set(live.BLOCKED) == {"HM", "HPM", "RDS", "SOL", "TB", "TBT", "BAT", "BB", "BRO", "CUT", "DTP"}

    class MCP:
        def __init__(self) -> None:
            self.names: list[str] = []

        def tool(self, *, name: str, annotations: Any) -> Any:
            del annotations
            self.names.append(name)
            return lambda function: function

    mcp = MCP()
    live.register_live_batch19_tools(mcp)  # type: ignore[arg-type]
    assert len(mcp.names) == 13
    assert [name for name in mcp.names if "execute" in name] == ["xicad_execute_live_cb"]
