from __future__ import annotations

from typing import Any

import pytest

from xicad_mcp import live_batch20 as live
from xicad_mcp.headless_core_batch1 import Point3D
from xicad_mcp.headless_core_batch20a import (
    CurveKind,
    CurveSnapshot,
    CutAlias,
    CutRequest,
    EditRole,
    IntersectionEvidence,
    ProposedCurveEdit,
)
from xicad_mcp.headless_core_batch20b import (
    CopyRotateRequest,
    CopyToCurrentLayerRequest,
    CopyToNewLayerRequest,
    DynamicArrayRequest,
    ExplicitCopy,
    LayerDefinition,
    LinearArrayRequest,
)


class Layer:
    def __init__(self, name: str, color: int = 7, linetype: str = "Continuous", lineweight: int = -3) -> None:
        self.Name, self.Color, self.Linetype, self.Lineweight, self.Lock = name, color, linetype, lineweight, False


class Layers:
    def __init__(self) -> None:
        self.items = [Layer("SRC"), Layer("CURRENT", 2)]

    def __iter__(self) -> Any:
        return iter(self.items)

    def Item(self, name: str) -> Layer:
        return next(item for item in self.items if item.Name.casefold() == name.casefold())

    def Add(self, name: str) -> Layer:
        item = Layer(name)
        self.items.append(item)
        return item


class Linetypes:
    def Item(self, name: str) -> str:
        if name not in {"Continuous", "HIDDEN"}:
            raise KeyError(name)
        return name


class Line:
    ObjectName = "AcDbLine"

    def __init__(self, doc: Doc, handle: str, start: Any, end: Any) -> None:
        self.doc = doc
        self.Handle, self.StartPoint, self.EndPoint = handle, start, end
        self.Layer, self.Color, self.Linetype, self.Lineweight, self.Thickness = "SRC", 1, "Continuous", -3, 0.5

    def Copy(self) -> Line:
        item = Line(self.doc, f"N{len(self.doc.entities)}", self.StartPoint, self.EndPoint)
        item.Layer, item.Color = self.Layer, self.Color
        item.Linetype, item.Lineweight, item.Thickness = self.Linetype, self.Lineweight, self.Thickness
        self.doc.entities.append(item)
        return item


class Doc:
    Name = "Drawing1.dwg"

    def __init__(self) -> None:
        self.Layers, self.Linetypes = Layers(), Linetypes()
        self.entities: list[Line] = [Line(self, "A", (0.0, 0.0, 0.0), (10.0, 0.0, 0.0))]
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


def wrapped(preview: dict[str, Any], request: Any) -> live.LiveCopyExecuteRequest:
    return live.LiveCopyExecuteRequest(
        request=request,
        expected_sources=tuple(live.LiveLineEvidence.model_validate(item) for item in preview["expected_sources"]),
        expected_target_layers=tuple(
            live.LiveLayerEvidence.model_validate(item) for item in preview["expected_target_layers"]
        ),
        approval_fingerprint=preview["approval_fingerprint"],
    )


def test_arv_line_copy_preview_execute_exact_translation(doc: Doc) -> None:
    request = LinearArrayRequest(
        document_id=doc.Name,
        source_handles=("A",),
        direction=Point3D(x=1, y=0),
        item_count=3,
        spacing=20,
    )
    preview = live.preview_live_arv(request)
    result = live.execute_live_copy(wrapped(preview, request))
    assert result.command_alias == "ARV" and result.created_handles == ("N1", "N2")
    assert [item.StartPoint for item in doc.entities[1:]] == [(20, 0, 0), (40, 0, 0)]
    assert all(item.Thickness == 0.5 for item in doc.entities[1:])


def test_cr_applies_copy_rotate_matrix_to_line_endpoints(doc: Doc) -> None:
    request = CopyRotateRequest(
        document_id=doc.Name,
        source_handles=("A",),
        base_point=Point3D(x=0, y=0),
        destination_point=Point3D(x=100, y=100),
        rotation_degrees=90,
    )
    preview = live.preview_live_cr(request)
    live.execute_live_copy(wrapped(preview, request))
    assert doc.entities[-1].StartPoint == pytest.approx((100, 100, 0))
    assert doc.entities[-1].EndPoint == pytest.approx((100, 110, 0))


def test_ctl_changes_only_target_layer_and_rejects_stale_source(doc: Doc) -> None:
    request = CopyToCurrentLayerRequest(
        document_id=doc.Name,
        source_handles=("A",),
        displacement=Point3D(x=5, y=5),
        current_layer="CURRENT",
    )
    preview = live.preview_live_ctl(request)
    approved = wrapped(preview, request)
    doc.entities[0].EndPoint = (20, 0, 0)
    with pytest.raises(ValueError, match="no longer matches"):
        live.execute_live_copy(approved)
    doc.entities[0].EndPoint = (10, 0, 0)
    result = live.execute_live_copy(approved)
    assert result.created_handles == ("N1",) and doc.entities[-1].Layer == "CURRENT"
    assert doc.entities[-1].Color == 1


def test_cnl_creates_exact_new_layer_and_copy(doc: Doc) -> None:
    request = CopyToNewLayerRequest(
        document_id=doc.Name,
        source_handles=("A",),
        displacement=Point3D(x=0, y=10),
        new_layer=LayerDefinition(name="NEW", color=3, linetype="HIDDEN", lineweight=25),
    )
    preview = live.preview_live_cnl(request)
    result = live.execute_live_copy(wrapped(preview, request))
    layer = doc.Layers.Item("NEW")
    assert result.created_layers == ("NEW",)
    assert (layer.Color, layer.Linetype, layer.Lineweight) == (3, "HIDDEN", 25)
    assert doc.entities[-1].Layer == "NEW"


def test_ard_explicit_affine_matrix_is_supported_for_line(doc: Doc) -> None:
    matrix = ((2.0, 0.0, 0.0, 1.0), (0.0, 1.0, 0.0, 2.0), (0.0, 0.0, 1.0, 0.0), (0.0, 0.0, 0.0, 1.0))
    request = DynamicArrayRequest(
        document_id=doc.Name,
        source_handles=("A",),
        copies=(ExplicitCopy(source_handle="A", transform=matrix),),
    )
    preview = live.preview_live_ard(request)
    live.execute_live_copy(wrapped(preview, request))
    assert doc.entities[-1].StartPoint == (1, 2, 0)
    assert doc.entities[-1].EndPoint == (21, 2, 0)


def test_cut_aliases_are_plan_visible_but_blocked_for_property_semantics() -> None:
    snapshots = (
        CurveSnapshot(handle="A", kind=CurveKind.LINE, vertices=(Point3D(x=0, y=0), Point3D(x=10, y=0)), layer="L"),
        CurveSnapshot(handle="B", kind=CurveKind.LINE, vertices=(Point3D(x=5, y=-5), Point3D(x=5, y=5)), layer="L"),
    )
    request = CutRequest(
        document_id="D",
        alias=CutAlias.FE,
        source_handles=("A", "B"),
        intersections=(IntersectionEvidence(point=Point3D(x=5, y=0), participating_handles=("A", "B")),),
        proposed_edits=(
            ProposedCurveEdit(source_handle="A", role=EditRole.TRIM, output_parts=((Point3D(x=0, y=0), Point3D(x=5, y=0)),)),
        ),
        retained_length=5,
        topology_tolerance=0.001,
        delete_originals=True,
    )
    preview = live.preview_live_cut(request, snapshots)
    assert preview["plan"]["command_alias"] == "FE"
    assert not preview["mutation"] and not preview["live_executable"]
    assert "output layer" in preview["blocked_reason"]


def test_registers_eighteen_tools_and_only_copy_aliases_execute() -> None:
    class MCP:
        def __init__(self) -> None:
            self.names: list[str] = []

        def tool(self, *, name: str, annotations: Any) -> Any:
            del annotations
            self.names.append(name)
            return lambda function: function

    mcp = MCP()
    live.register_live_batch20_tools(mcp)  # type: ignore[arg-type]
    assert len(mcp.names) == 18
    assert len([name for name in mcp.names if "execute" in name]) == 6
    assert all(alias in " ".join(mcp.names) for alias in ("ard", "arp", "arv", "cnl", "cr", "ctl"))
