from __future__ import annotations

from typing import Any

import pytest

from xicad_mcp import live_batch21 as live
from xicad_mcp.headless_core_batch1 import Point3D
from xicad_mcp.headless_core_batch21a import ExtendLineRequest, LineAnchor, MultiCopyRequest
from xicad_mcp.headless_core_batch21b import BothSidesOffsetRequest, OffsetOutput


class Layer:
    def __init__(self, name: str) -> None:
        self.Name, self.Lock = name, False


class Layers:
    def __init__(self) -> None:
        self.items = {name: Layer(name) for name in ("SRC", "OUT")}

    def Item(self, name: str) -> Layer:
        return self.items[name]


class Line:
    ObjectName = "AcDbLine"

    def __init__(self, doc: Doc, handle: str, start: Any, end: Any, layer: str = "SRC") -> None:
        self.doc, self.Handle, self.StartPoint, self.EndPoint, self.Layer = doc, handle, start, end, layer
        self.Color, self.Linetype, self.Lineweight, self.Thickness = 1, "Continuous", -3, 0.0

    def Copy(self) -> Line:
        result = Line(self.doc, f"N{len(self.doc.entities)}", self.StartPoint, self.EndPoint, self.Layer)
        self.doc.entities.append(result)
        return result

    def Delete(self) -> None:
        self.doc.entities.remove(self)


class Space:
    def __init__(self, doc: Doc) -> None:
        self.doc = doc

    def AddLine(self, start: Any, end: Any) -> Line:
        result = Line(self.doc, f"N{len(self.doc.entities)}", start, end, "0")
        self.doc.entities.append(result)
        return result


class Doc:
    Name = "Drawing1.dwg"

    def __init__(self) -> None:
        self.Layers, self.entities, self.marks = Layers(), [], []
        self.entities.append(Line(self, "A", (0.0, 0.0, 0.0), (10.0, 0.0, 0.0)))
        self.ModelSpace = Space(self)

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


def approved(preview: dict[str, Any], request: Any) -> live.LiveBatch21ExecuteRequest:
    return live.LiveBatch21ExecuteRequest(
        request=request,
        expected_sources=tuple(live.LiveLineEvidence.model_validate(item) for item in preview["expected_sources"]),
        approval_fingerprint=preview["approval_fingerprint"],
    )


def test_mc_preview_execute_and_stale_detection(doc: Doc) -> None:
    request = MultiCopyRequest(
        document_id=doc.Name,
        source_handles=("A",),
        displacement=Point3D(x=20, y=0),
        copy_count=2,
        include_original_position=False,
    )
    preview = live.preview_live_mc(request)
    wrapped = approved(preview, request)
    doc.entities[0].EndPoint = (11.0, 0.0, 0.0)
    with pytest.raises(ValueError, match="no longer matches"):
        live.execute_live_batch21(wrapped)
    doc.entities[0].EndPoint = (10.0, 0.0, 0.0)
    result = live.execute_live_batch21(wrapped)
    assert result.created_handles == ("N1", "N2")
    assert doc.entities[-1].EndPoint == (50.0, 0.0, 0.0)
    assert doc.marks == ["start", "end"]


def test_exl_exact_endpoint_change(doc: Doc) -> None:
    request = ExtendLineRequest(document_id=doc.Name, target_handles=("A",), anchor=LineAnchor.START, target_length=25)
    preview = live.preview_live_exl(request)
    result = live.execute_live_batch21(approved(preview, request))
    assert result.changed_handles == ("A",)
    assert doc.entities[0].EndPoint == (25.0, 0.0, 0.0)


def test_ob_creates_explicit_linework_on_target_layer(doc: Doc) -> None:
    request = BothSidesOffsetRequest(
        document_id=doc.Name,
        source_handle="A",
        distance=5,
        positive_side=OffsetOutput(
            source_handles=("A",), vertices=(Point3D(x=0, y=5), Point3D(x=10, y=5)), layer="OUT"
        ),
        negative_side=OffsetOutput(
            source_handles=("A",), vertices=(Point3D(x=0, y=-5), Point3D(x=10, y=-5)), layer="OUT"
        ),
    )
    preview = live.preview_live_ob(request)
    result = live.execute_live_batch21(approved(preview, request))
    assert len(result.created_handles) == 2
    assert all(item.Layer == "OUT" for item in doc.entities[1:])


def test_registers_twelve_previews_and_nine_execute_tools() -> None:
    class MCP:
        def __init__(self) -> None:
            self.names: list[str] = []

        def tool(self, *, name: str, annotations: Any) -> Any:
            del annotations
            self.names.append(name)
            return lambda function: function

    mcp = MCP()
    live.register_live_batch21_tools(mcp)  # type: ignore[arg-type]
    assert len(mcp.names) == 21
    assert len([name for name in mcp.names if "execute" in name]) == 9
    assert not any(f"execute_live_{alias}" in " ".join(mcp.names) for alias in ("mm", "jl", "mlc"))
