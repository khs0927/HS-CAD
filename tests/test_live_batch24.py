from __future__ import annotations

from typing import Any

import pytest

from xicad_mcp import live_batch24 as live
from xicad_mcp.headless_core_batch1 import Point3D
from xicad_mcp.headless_core_batch24a import (
    DistanceMemoryRequest,
    PolylineLengthSnapshot,
    RectangleAreaLabelRequest,
    RectangleSnapshot,
    TextAnchor,
)
from xicad_mcp.headless_core_batch24b import AnnotationMode, HwAreaRequest, ProposedTriangleAnnotation, TriangleSnapshot


class Layer:
    def __init__(self, name: str) -> None:
        self.Name, self.Lock = name, False


class Layers:
    def __init__(self) -> None:
        self.items = {name: Layer(name) for name in ("SOURCE", "ANNO")}

    def Item(self, name: str) -> Layer:
        return self.items[name]


class Entity:
    ObjectName = "AcDbPolyline"

    def __init__(self, handle: str) -> None:
        self.Handle, self.Layer = handle, "SOURCE"
        self.Coordinates = (0.0, 0.0, 4.0, 0.0, 4.0, 3.0, 0.0, 3.0)
        self.Closed = True


class Text:
    ObjectName = "AcDbMText"

    def __init__(self, handle: str, point: tuple[float, float, float], text: str = "OLD") -> None:
        self.Handle, self.Layer = handle, "ANNO"
        self.InsertionPoint, self.TextString = point, text
        self.Height, self.AttachmentPoint = 2.5, 1


class ModelSpace:
    def __init__(self, doc: Doc) -> None:
        self.doc = doc

    def AddMText(self, point: tuple[float, float, float], width: float, text: str) -> Text:
        assert width == 0.0
        entity = Text(f"N{len(self.doc.entities)}", point, text)
        self.doc.entities.append(entity)
        return entity


class Doc:
    Name = "Drawing1.dwg"

    def __init__(self) -> None:
        self.Layers = Layers()
        self.entities: list[Any] = [Entity("P1"), Text("T1", (9.0, 8.0, 0.0))]
        self.ModelSpace = ModelSpace(self)
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


def approved(preview: dict[str, Any], request: Any) -> live.LiveBatch24ExecuteRequest:
    replacement = preview["expected_replacement_text"]
    return live.LiveBatch24ExecuteRequest(
        request=request,
        expected_sources=tuple(live.LiveEntityEvidence.model_validate(item) for item in preview["expected_sources"]),
        expected_replacement_text=None if replacement is None else live.LiveTextEvidence.model_validate(replacement),
        expected_target_layer=live.LiveLayerEvidence.model_validate(preview["expected_target_layer"]),
        approval_fingerprint=preview["approval_fingerprint"],
    )


def test_hv_preview_execute_creates_exact_anchored_mtext(doc: Doc) -> None:
    request = RectangleAreaLabelRequest(
        document_id=doc.Name,
        rectangles=(RectangleSnapshot(source_handle="P1", width=4, height=3),),
        insertion_point=Point3D(x=100, y=200),
        anchor=TextAnchor.MIDDLE_CENTER,
        layer="ANNO",
        text_height=25,
    )
    preview = live.preview_live_hv(request)
    result = live.execute_live_batch24(approved(preview, request))
    output = doc.entities[-1]
    assert result.command_alias == "HV" and result.created_handles == (output.Handle,)
    assert output.TextString == preview["plan"]["labels"][0]["text"]
    assert output.InsertionPoint == (100, 200, 0) and output.Height == 25
    assert output.Layer == "ANNO" and output.AttachmentPoint == 5
    assert doc.marks == ["start", "end"] and result.postcondition_verified


def _hw_request(mode: AnnotationMode) -> HwAreaRequest:
    return HwAreaRequest(
        document_id="Drawing1.dwg",
        triangle=TriangleSnapshot(
            source_id="P1",
            horizontal_length=6,
            vertical_length=4,
            geometry_revision="rev-1",
        ),
        annotation_mode=mode,
        exact_annotation=ProposedTriangleAnnotation(
            formula_text="6 x 4 / 2",
            result_text="12.00 m2",
            reported_area=12,
            text_height=20,
            layer="ANNO",
            insertion_point=Point3D(x=50, y=60) if mode is AnnotationMode.CREATE_TEXT else None,
            replace_text_handle="T1" if mode is AnnotationMode.REPLACE_TEXT else None,
        ),
    )


def test_hw_create_mode_creates_exact_mtext(doc: Doc) -> None:
    request = _hw_request(AnnotationMode.CREATE_TEXT)
    preview = live.preview_live_hw(request)
    result = live.execute_live_batch24(approved(preview, request))
    output = doc.entities[-1]
    assert result.created_handles == (output.Handle,) and not result.changed_handles
    assert output.TextString == "6 x 4 / 2\n12.00 m2"
    assert output.InsertionPoint == (50, 60, 0) and output.Height == 20


def test_hw_replace_mode_stale_checks_and_changes_only_approved_text(doc: Doc) -> None:
    request = _hw_request(AnnotationMode.REPLACE_TEXT)
    preview = live.preview_live_hw(request)
    wrapped = approved(preview, request)
    target = doc.entities[1]
    target.TextString = "STALE"
    with pytest.raises(ValueError, match="replacement text no longer matches"):
        live.execute_live_batch24(wrapped)
    target.TextString = "OLD"
    result = live.execute_live_batch24(wrapped)
    assert result.changed_handles == ("T1",) and not result.created_handles
    assert target.TextString == "6 x 4 / 2\n12.00 m2" and target.InsertionPoint == (9, 8, 0)


def test_bad_fingerprint_and_stale_source_are_rejected(doc: Doc) -> None:
    request = _hw_request(AnnotationMode.CREATE_TEXT)
    wrapped = approved(live.preview_live_hw(request), request)
    bad = wrapped.model_copy(update={"approval_fingerprint": "sha256:" + "0" * 64})
    with pytest.raises(ValueError, match="fingerprint"):
        live.execute_live_batch24(bad)
    doc.entities[0].Coordinates = (0.0, 0.0, 5.0, 0.0, 5.0, 3.0, 0.0, 3.0)
    with pytest.raises(ValueError, match="source state no longer matches"):
        live.execute_live_batch24(wrapped)


def test_dm_preview_is_non_mutating_and_explains_legacy_memory_blocker() -> None:
    request = DistanceMemoryRequest(
        document_id="Drawing1.dwg",
        polyline=PolylineLengthSnapshot(polyline_handle="P1", measured_length=12.5),
        memory_slot="slot-a",
    )
    preview = live.preview_live_dm(request)
    assert preview["command_alias"] == "DM"
    assert not preview["mutation"] and not preview["live_executable"]
    assert "memory" in preview["blocked_reason"]


def test_registers_twelve_previews_and_only_hv_hw_execute() -> None:
    class MCP:
        def __init__(self) -> None:
            self.names: list[str] = []

        def tool(self, *, name: str, annotations: Any) -> Any:
            del annotations
            self.names.append(name)
            return lambda function: function

    mcp = MCP()
    live.register_live_batch24_tools(mcp)  # type: ignore[arg-type]
    previews = [name for name in mcp.names if "preview" in name]
    executes = [name for name in mcp.names if "execute" in name]
    assert len(previews) == 12
    assert executes == ["xicad_execute_live_hv", "xicad_execute_live_hw"]
    assert all(
        alias in " ".join(previews)
        for alias in ("cdn", "dar", "dee", "dm", "ffo", "hv", "hw", "mac", "mrt", "sar", "sca", "se")
    )
