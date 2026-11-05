from __future__ import annotations

from typing import Any

import pytest

from xicad_mcp import live_batch15b as live
from xicad_mcp.headless_core_batch1 import Point3D
from xicad_mcp.headless_core_batch15 import (
    ClosePolicy,
    ExplorerRequest,
    FrameSize,
    LayerCreateSpec,
    OpenDrawingRequest,
    QuickQuitRequest,
    StartRequest,
    SteelKind,
    SteelRequest,
    SteelView,
)


class FakeLayer:
    def __init__(self, name: str, color: int = 7, linetype: str = "Continuous") -> None:
        self.Name = name
        self.Color = color
        self.Linetype = linetype
        self.Lock = False


class FakeLayers:
    def __init__(self) -> None:
        self.items = [FakeLayer("0"), FakeLayer("STEEL", 2)]

    def __iter__(self) -> Any:
        return iter(self.items)

    def Item(self, name: str) -> FakeLayer:
        return next(item for item in self.items if item.Name.casefold() == name.casefold())

    def Add(self, name: str) -> FakeLayer:
        layer = FakeLayer(name)
        self.items.append(layer)
        return layer


class FakeLinetypes:
    def Item(self, name: str) -> str:
        if name.casefold() not in {"continuous", "hidden"}:
            raise KeyError(name)
        return name


class FakePolyline:
    ObjectName = "AcDbPolyline"

    def __init__(self, handle: str, coordinates: list[float]) -> None:
        self.Handle = handle
        self.Coordinates = coordinates
        self.Elevation = 0.0
        self.Layer = "0"
        self.Closed = False


class FakeModelSpace:
    def __init__(self, doc: FakeDoc) -> None:
        self.doc = doc

    def AddLightWeightPolyline(self, coordinates: list[float]) -> FakePolyline:
        entity = FakePolyline(f"N{len(self.doc.entities)}", list(coordinates))
        self.doc.entities.append(entity)
        return entity


class FakeDoc:
    FullName = r"C:\work\Drawing1.dwg"
    Saved = False
    ReadOnly = False

    def __init__(self, name: str = "Drawing1.dwg") -> None:
        self.Name = name
        self.Layers = FakeLayers()
        self.Linetypes = FakeLinetypes()
        self.ModelSpace = FakeModelSpace(self)
        self.entities: list[FakePolyline] = []
        self.variables = {"LTSCALE": 1.0, "DIMSCALE": 1.0}
        self.marks: list[str] = []

    def Activate(self) -> None:
        pass

    def GetVariable(self, name: str) -> float:
        return self.variables[name]

    def SetVariable(self, name: str, value: float) -> None:
        self.variables[name] = value

    def StartUndoMark(self) -> None:
        self.marks.append("start")

    def EndUndoMark(self) -> None:
        self.marks.append("end")


class FakeApp:
    def __init__(self, docs: list[FakeDoc]) -> None:
        self.Documents = docs


@pytest.fixture
def doc(monkeypatch: pytest.MonkeyPatch) -> FakeDoc:
    drawing = FakeDoc()
    app = FakeApp([drawing])
    monkeypatch.setattr(live, "_application", lambda: app)
    monkeypatch.setattr(live, "_entities", lambda _doc: {item.Handle.casefold(): item for item in drawing.entities})
    monkeypatch.setattr(
        live,
        "_variant_coordinates",
        lambda points: [coordinate for point in points for coordinate in (point.x, point.y)],
    )
    return drawing


def stt_request() -> StartRequest:
    return StartRequest(
        document_id="Drawing1.dwg",
        drawing_scale=50,
        apply_ltscale=True,
        apply_dimscale=True,
        create_layers=(LayerCreateSpec(name="ANNO", color=3, linetype="Continuous"),),
        frame_size=FrameSize.NONE,
    )


def test_stt_preview_and_execute_exact_setup(doc: FakeDoc) -> None:
    request = stt_request()
    preview = live.preview_live_stt(request)
    wrapped = live.LiveSttExecuteRequest(
        request=request,
        expected_variables=preview["expected_variables"],
        expected_layers=tuple(live.LiveLayerState.model_validate(item) for item in preview["expected_layers"]),
        approval_fingerprint=preview["approval_fingerprint"],
    )
    result = live.execute_live_stt(wrapped)
    state = live._layer_state(doc, "ANNO")
    assert doc.variables == {"LTSCALE": 50, "DIMSCALE": 50}
    assert (state.exists, state.color, state.linetype) == (True, 3, "Continuous")
    assert result.postcondition_verified and doc.marks == ["start", "end"]


def test_stt_stale_variable_is_rejected(doc: FakeDoc) -> None:
    request = stt_request()
    preview = live.preview_live_stt(request)
    wrapped = live.LiveSttExecuteRequest(
        request=request,
        expected_variables=preview["expected_variables"],
        expected_layers=tuple(live.LiveLayerState.model_validate(item) for item in preview["expected_layers"]),
        approval_fingerprint=preview["approval_fingerprint"],
    )
    doc.variables["DIMSCALE"] = 2
    with pytest.raises(ValueError, match="no longer matches"):
        live.execute_live_stt(wrapped)


def test_stt_blocks_reference_and_frame_semantics(doc: FakeDoc) -> None:
    reference = stt_request().model_copy(update={"reference_file": r"C:\x\ref.dwg"})
    with pytest.raises(ValueError, match="reference attachment"):
        live.preview_live_stt(reference)
    frame = stt_request().model_copy(
        update={"frame_size": FrameSize.A3, "frame_file": r"C:\x\a3.dwg", "insertion_point": Point3D(x=0, y=0)}
    )
    with pytest.raises(ValueError, match="frame insertion"):
        live.preview_live_stt(frame)


def steel_request() -> SteelRequest:
    return SteelRequest(
        document_id="Drawing1.dwg",
        kind=SteelKind.H_BEAM,
        view=SteelView.SECTION,
        insertion_point=Point3D(x=100, y=100),
        depth=200,
        width=100,
        web_thickness=6,
        flange_thickness=9,
        section_layer="STEEL",
        elevation_layer="STEEL",
        hidden_layer="0",
        square_corners=True,
    )


def test_be_preview_and_execute_exact_planned_envelope(doc: FakeDoc) -> None:
    request = steel_request()
    preview = live.preview_live_be(request)
    wrapped = live.LiveBeExecuteRequest(
        request=request,
        expected_layer=live.LiveLayerState.model_validate(preview["expected_layer"]),
        approval_fingerprint=preview["approval_fingerprint"],
    )
    result = live.execute_live_be(wrapped)
    assert doc.entities[0].Coordinates == [50, 0, 150, 0, 150, 200, 50, 200]
    assert doc.entities[0].Closed and doc.entities[0].Layer == "STEEL"
    assert result.created_handles == ("N0",)


def test_be_stale_layer_rejected(doc: FakeDoc) -> None:
    request = steel_request()
    preview = live.preview_live_be(request)
    wrapped = live.LiveBeExecuteRequest(
        request=request,
        expected_layer=live.LiveLayerState.model_validate(preview["expected_layer"]),
        approval_fingerprint=preview["approval_fingerprint"],
    )
    doc.Layers.Item("STEEL").Color = 4
    with pytest.raises(ValueError, match="no longer matches"):
        live.execute_live_be(wrapped)


def test_exp_ol_on_are_deterministic_blocked_previews(doc: FakeDoc) -> None:
    exp = live.preview_live_exp(
        ExplorerRequest(document_id=doc.Name, drawing_path=r"C:\work\Drawing1.dwg")
    )
    assert exp["folder_path"] == r"C:\work"
    assert "Undo boundary" in exp["blocked_reason"]
    candidates = (r"C:\work\Drawing1.dwg", r"C:\work\Drawing2.dwg")
    ol = live.preview_live_ol(
        OpenDrawingRequest(
            document_id=doc.Name,
            current_path=candidates[0],
            candidate_paths=candidates,
            selected_path=candidates[1],
            read_only=True,
            operation="list_select",
        )
    )
    on = live.preview_live_on(
        OpenDrawingRequest(
            document_id=doc.Name,
            current_path=candidates[0],
            candidate_paths=candidates,
            read_only=False,
            operation="next",
        )
    )
    assert (ol["target_path"], on["target_path"]) == (candidates[1], candidates[1])
    assert not ol["mutation"] and not on["mutation"]


def test_qq_snapshots_open_document_but_exposes_no_executor(doc: FakeDoc) -> None:
    preview = live.preview_live_qq(
        QuickQuitRequest(
            document_id=doc.Name,
            target_document_ids=(doc.Name,),
            policy=ClosePolicy.SAVE_MODIFIED,
        )
    )
    assert preview["expected_documents"][0]["modified"]
    assert preview["actions"][0]["save_before_close"]
    assert "cannot be restored" in preview["blocked_reason"]


def test_registers_two_live_aliases_and_four_blocked_previews() -> None:
    class MCP:
        def __init__(self) -> None:
            self.names: list[str] = []

        def tool(self, *, name: str, annotations: Any) -> Any:
            del annotations
            self.names.append(name)
            return lambda function: function

    mcp = MCP()
    live.register_live_batch15b_tools(mcp)  # type: ignore[arg-type]
    assert len(mcp.names) == 8
    assert {"xicad_execute_live_stt", "xicad_execute_live_be"} <= set(mcp.names)
    assert not any(name.startswith("xicad_execute_live_q") for name in mcp.names)
