from __future__ import annotations

from datetime import date
from typing import Any

import pytest

from xicad_mcp import live_batch15a as live
from xicad_mcp.headless_core_batch1 import Point3D
from xicad_mcp.headless_core_batch15 import ContentKind, CopyContentsRequest, DateStampRequest, FlattenRequest


class ItemCollection:
    def __init__(self, items: dict[str, Any]) -> None:
        self.items = items

    def Item(self, name: str) -> Any:
        return self.items[name]


class Layer:
    def __init__(self, name: str, lock: bool = False) -> None:
        self.Name, self.Lock = name, lock


class Entity:
    def __init__(self, handle: str, text: str | None = None, width: float | None = None) -> None:
        self.Handle, self.Layer = handle, "TEXT"
        if text is not None:
            self.ObjectName, self.TextString = "AcDbText", text
        else:
            self.ObjectName, self.ConstantWidth = "AcDbPolyline", width


class Line(Entity):
    def __init__(self, handle: str, start: tuple[float, float, float], end: tuple[float, float, float]) -> None:
        self.Handle, self.Layer, self.ObjectName = handle, "TEXT", "AcDbLine"
        self.StartPoint, self.EndPoint = start, end


class ModelSpace:
    def __init__(self, doc: Doc) -> None:
        self.doc = doc

    def AddText(self, text: str, point: tuple[float, float, float], height: float) -> Any:
        del point
        entity = Entity(f"N{len(self.doc.entities)}", text=text)
        entity.Height, entity.StyleName = height, "Standard"
        self.doc.entities.append(entity)
        return entity


class Doc:
    Name = "Drawing1.dwg"

    def __init__(self) -> None:
        self.entities = [Entity("S", text="SOURCE"), Entity("T", text="old")]
        self.Layers = ItemCollection({"TEXT": Layer("TEXT")})
        self.TextStyles = ItemCollection({"Standard": object()})
        self.ModelSpace = ModelSpace(self)
        self.marks: list[str] = []

    def StartUndoMark(self) -> None: self.marks.append("start")
    def EndUndoMark(self) -> None: self.marks.append("end")


@pytest.fixture
def doc(monkeypatch: pytest.MonkeyPatch) -> Doc:
    drawing = Doc()
    monkeypatch.setattr(live, "_drawing", lambda _name: drawing)
    monkeypatch.setattr(live, "_entities", lambda _doc: {item.Handle.casefold(): item for item in drawing.entities})
    monkeypatch.setattr(live, "_variant", lambda point: (point.x, point.y, point.z))
    return drawing


def test_ct_copies_exact_text_with_stale_check_and_undo(doc: Doc) -> None:
    request = CopyContentsRequest(document_id=doc.Name, source_handle="S", target_handles=("T",), expected_kind=ContentKind.TEXT)
    preview = live.preview_live_ct(request)
    wrapped = live.LiveCtExecuteRequest(
        request=request,
        expected_contents=tuple(live.LiveContentEvidence.model_validate(item) for item in preview["expected_contents"]),
        approval_fingerprint=preview["approval_fingerprint"],
    )
    doc.entities[1].TextString = "changed"
    with pytest.raises(ValueError, match="no longer matches"):
        live.execute_live_ct(wrapped)
    doc.entities[1].TextString = "old"
    result = live.execute_live_ct(wrapped)
    assert result.changed_handles == ("T",) and doc.entities[1].TextString == "SOURCE"
    assert doc.marks == ["start", "end"]


def test_ct_copies_polyline_width_and_blocks_circle_replacement(doc: Doc) -> None:
    doc.entities = [Entity("S", width=2.5), Entity("T", width=0.0)]
    request = CopyContentsRequest(document_id=doc.Name, source_handle="S", target_handles=("T",), expected_kind=ContentKind.POLYLINE_WIDTH)
    preview = live.preview_live_ct(request)
    result = live.execute_live_ct(live.LiveCtExecuteRequest(
        request=request,
        expected_contents=tuple(live.LiveContentEvidence.model_validate(item) for item in preview["expected_contents"]),
        approval_fingerprint=preview["approval_fingerprint"],
    ))
    assert result.postcondition_verified and doc.entities[1].ConstantWidth == 2.5
    blocked = request.model_copy(update={"expected_kind": ContentKind.CIRCLE_DIAMETER})
    with pytest.raises(ValueError, match="circle/block replacement"):
        live.preview_live_ct(blocked)


def test_dts_creates_exact_text_and_rejects_locked_layer(doc: Doc) -> None:
    request = DateStampRequest(
        document_id=doc.Name, creation_date=date(2026, 7, 22), insertion_point=Point3D(x=10, y=20),
        format_template="%Y-%m-%d", prefix="CREATED ", layer="TEXT", text_style="Standard", text_height=300,
    )
    preview = live.preview_live_dts(request)
    wrapped = live.LiveDtsExecuteRequest(
        request=request,
        expected_layer=live.LiveLayerEvidence.model_validate(preview["expected_layer"]),
        approval_fingerprint=preview["approval_fingerprint"],
    )
    result = live.execute_live_dts(wrapped)
    output = doc.entities[-1]
    assert result.created_handles == ("N2",)
    assert (output.TextString, output.Height, output.Layer, output.StyleName) == ("CREATED 2026-07-22", 300, "TEXT", "Standard")
    doc.Layers.items["TEXT"].Lock = True
    with pytest.raises(ValueError, match="locked"):
        live.preview_live_dts(request)


def test_bad_fingerprints_and_registration(doc: Doc) -> None:
    request = CopyContentsRequest(document_id=doc.Name, source_handle="S", target_handles=("T",), expected_kind=ContentKind.TEXT)
    preview = live.preview_live_ct(request)
    wrapped = live.LiveCtExecuteRequest(
        request=request,
        expected_contents=tuple(live.LiveContentEvidence.model_validate(item) for item in preview["expected_contents"]),
        approval_fingerprint="sha256:" + "0" * 64,
    )
    with pytest.raises(ValueError, match="fingerprint"):
        live.execute_live_ct(wrapped)

    class MCP:
        def __init__(self) -> None: self.names: list[str] = []
        def tool(self, *, name: str, annotations: Any) -> Any:
            del annotations
            self.names.append(name)
            return lambda function: function

    mcp = MCP()
    live.register_live_batch15a_tools(mcp)  # type: ignore[arg-type]
    assert mcp.names == [
        "xicad_preview_live_ct", "xicad_execute_live_ct", "xicad_preview_live_dts", "xicad_execute_live_dts",
        "xicad_preview_live_flt", "xicad_execute_live_flt",
    ]


def test_flt_flattens_exact_line_endpoints_and_rejects_unsupported_type(doc: Doc) -> None:
    doc.entities = [Line("L1", (0, 0, 7), (5, 2, -3))]
    request = FlattenRequest(document_id=doc.Name, target_handles=("L1",), target_z=0)
    preview = live.preview_live_flt(request)
    wrapped = live.LiveFltExecuteRequest(
        request=request,
        expected_geometry=tuple(live.LiveGeometryEvidence.model_validate(item) for item in preview["expected_geometry"]),
        approval_fingerprint=preview["approval_fingerprint"],
    )
    result = live.execute_live_flt(wrapped)
    assert result.changed_handles == ("L1",)
    assert doc.entities[0].StartPoint == (0.0, 0.0, 0.0)
    assert doc.entities[0].EndPoint == (5.0, 2.0, 0.0)
    doc.entities = [Entity("P1", width=0)]
    blocked = request.model_copy(update={"target_handles": ("P1",)})
    with pytest.raises(ValueError, match="AcDbLine"):
        live.preview_live_flt(blocked)
