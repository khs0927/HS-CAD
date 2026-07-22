from __future__ import annotations

from typing import Any

import pytest

from xicad_mcp import live_batch26 as live
from xicad_mcp.headless_core_batch1 import Point3D
from xicad_mcp.headless_core_batch26a import (
    PolylineJoinRequest,
    PolylineSnapshot,
    PolylineVertex,
    PolylineWidthRequest,
    ProposedPolylineResult,
    VertexAddRequest,
    VertexDeleteRequest,
    VertexRemoveCleanRequest,
)
from xicad_mcp.headless_core_batch26b import (
    ProposedPolyline,
    SolidRectangleRequest,
    ThreePointRectangleRequest,
    VSymbolRequest,
)


class Layer:
    def __init__(self, name: str, locked: bool = False) -> None:
        self.Name, self.Lock = name, locked


class Layers:
    def __init__(self) -> None:
        self.items = {name: Layer(name) for name in ("SOURCE", "OUTPUT")}

    def Item(self, name: str) -> Layer:
        return self.items[name]


class Polyline:
    ObjectName = "AcDbPolyline"

    def __init__(
        self,
        handle: str,
        coordinates: tuple[float, ...],
        *,
        layer: str = "SOURCE",
        closed: bool = False,
    ) -> None:
        self.Handle, self.Coordinates = handle, coordinates
        self.Layer, self.Closed = layer, closed
        self.Color, self.Linetype, self.LinetypeScale, self.Lineweight = 7, "ByLayer", 1.0, -1
        count = len(coordinates) // 2
        self.bulges = [0.0] * count
        self.widths = [(0.0, 0.0)] * count
        self.deleted = False

    def Delete(self) -> None:
        self.deleted = True

    def GetBulge(self, index: int) -> float:
        return self.bulges[index]

    def SetBulge(self, index: int, value: float) -> None:
        self._resize()
        self.bulges[index] = value

    def GetWidth(self, index: int) -> tuple[float, float]:
        return self.widths[index]

    def SetWidth(self, index: int, start: float, end: float) -> None:
        self._resize()
        self.widths[index] = (start, end)

    def _resize(self) -> None:
        count = len(self.Coordinates) // 2
        self.bulges = (self.bulges + [0.0] * count)[:count]
        self.widths = (self.widths + [(0.0, 0.0)] * count)[:count]


class Solid:
    ObjectName = "AcDbSolid"

    def __init__(self, handle: str, points: tuple[tuple[float, float, float], ...]) -> None:
        self.Handle, self.Layer, self.Color = handle, "0", 7
        self.Coordinates = tuple(value for point in points for value in point)


class ModelSpace:
    def __init__(self, doc: Doc) -> None:
        self.doc = doc

    def AddLightWeightPolyline(self, coordinates: tuple[float, ...]) -> Polyline:
        entity = Polyline(f"N{len(self.doc.entities)}", coordinates, layer="0")
        self.doc.entities.append(entity)
        return entity

    def AddSolid(self, *points: tuple[float, float, float]) -> Solid:
        entity = Solid(f"N{len(self.doc.entities)}", points)
        self.doc.entities.append(entity)
        return entity


class Doc:
    Name = "Drawing1.dwg"

    def __init__(self) -> None:
        self.Layers = Layers()
        self.entities: list[Any] = [Polyline("P1", (0, 0, 4, 0, 4, 3))]
        self.ModelSpace = ModelSpace(self)
        self.marks: list[str] = []

    def StartUndoMark(self) -> None:
        self.marks.append("start")

    def EndUndoMark(self) -> None:
        self.marks.append("end")


def vertex(vertex_id: str, x: float, y: float, *, width: float = 0) -> PolylineVertex:
    return PolylineVertex(
        vertex_id=vertex_id,
        point=Point3D(x=x, y=y),
        start_width=width,
        end_width=width,
    )


def snapshot() -> PolylineSnapshot:
    return PolylineSnapshot(
        handle="P1",
        entity_type="LWPOLYLINE",
        geometry_revision="r1",
        layer="SOURCE",
        closed=False,
        vertices=(vertex("a", 0, 0), vertex("b", 4, 0), vertex("c", 4, 3)),
    )


def result(vertices: tuple[PolylineVertex, ...], *, layer: str = "OUTPUT") -> ProposedPolylineResult:
    return ProposedPolylineResult(
        result_id="result-1",
        source_handles=("P1",),
        entity_type="LWPOLYLINE",
        layer=layer,
        closed=False,
        vertices=vertices,
    )


@pytest.fixture
def doc(monkeypatch: pytest.MonkeyPatch) -> Doc:
    drawing = Doc()
    monkeypatch.setattr(live, "_drawing", lambda _name: drawing)
    monkeypatch.setattr(
        live,
        "_entities",
        lambda _doc: {
            item.Handle.casefold(): item for item in drawing.entities if not getattr(item, "deleted", False)
        },
    )
    monkeypatch.setattr(
        live, "_variant_points", lambda points: tuple(value for point in points for value in (point.x, point.y))
    )
    monkeypatch.setattr(live, "_variant_point", lambda point: (point.x, point.y, point.z))
    return drawing


def approved(preview: dict[str, Any], request: Any) -> live.LiveBatch26ExecuteRequest:
    return live.LiveBatch26ExecuteRequest(
        request=request,
        expected_sources=tuple(live.LivePolylineEvidence.model_validate(item) for item in preview["expected_sources"]),
        expected_target_layers=tuple(
            live.LiveLayerEvidence.model_validate(item) for item in preview["expected_target_layers"]
        ),
        approval_fingerprint=preview["approval_fingerprint"],
    )


@pytest.mark.parametrize(
    ("request_type", "vertices", "alias"),
    [
        (VertexAddRequest, (vertex("a", 0, 0), vertex("x", 2, 0), vertex("b", 4, 0), vertex("c", 4, 3)), "PV"),
        (VertexRemoveCleanRequest, (vertex("a", 0, 0), vertex("c", 4, 3)), "PVR"),
        (VertexDeleteRequest, (vertex("a", 0, 0), vertex("b", 4, 0)), "PVV"),
    ],
)
def test_vertex_edits_replace_exact_topology_with_undo(
    doc: Doc,
    request_type: type[Any],
    vertices: tuple[PolylineVertex, ...],
    alias: str,
) -> None:
    request = request_type(document_id=doc.Name, source=snapshot(), exact_result=result(vertices))
    preview_function = {"PV": live.preview_live_pv, "PVR": live.preview_live_pvr, "PVV": live.preview_live_pvv}[alias]
    execution = live.execute_live_batch26(approved(preview_function(request), request))
    entity = doc.entities[0]
    assert execution.command_alias == alias and execution.changed_handles == ("P1",)
    assert entity.Coordinates == tuple(value for item in vertices for value in (item.point.x, item.point.y))
    assert entity.Layer == "OUTPUT" and doc.marks == ["start", "end"]
    assert (entity.Color, entity.Linetype, entity.LinetypeScale, entity.Lineweight) == (7, "ByLayer", 1.0, -1)


def test_pw_changes_only_exact_widths_and_stale_checks_full_topology(doc: Doc) -> None:
    vertices = tuple(item.model_copy(update={"start_width": 2.0, "end_width": 3.0}) for item in snapshot().vertices)
    request = PolylineWidthRequest(
        document_id=doc.Name, source=snapshot(), exact_result=result(vertices, layer="SOURCE")
    )
    preview = live.preview_live_pw(request)
    wrapped = approved(preview, request)
    doc.entities[0].widths[1] = (9.0, 9.0)
    with pytest.raises(ValueError, match="state no longer matches"):
        live.execute_live_batch26(wrapped)
    doc.entities[0].widths[1] = (0.0, 0.0)
    execution = live.execute_live_batch26(wrapped)
    assert execution.postcondition_verified
    assert doc.entities[0].widths == [(2.0, 3.0)] * 3


def test_r3_and_v_create_exact_polylines(doc: Doc) -> None:
    rectangle = ProposedPolyline(
        vertices=(Point3D(x=10, y=10), Point3D(x=14, y=10), Point3D(x=14, y=13), Point3D(x=10, y=13)),
        closed=True,
        layer="OUTPUT",
    )
    r3 = ThreePointRectangleRequest(
        document_id=doc.Name,
        picked_points=(Point3D(x=10, y=10), Point3D(x=14, y=10), Point3D(x=14, y=13)),
        exact_rectangle=rectangle,
    )
    r3_result = live.execute_live_batch26(approved(live.preview_live_r3(r3), r3))
    assert r3_result.created_handles == ("N1",) and doc.entities[-1].Closed
    v_request = VSymbolRequest(
        document_id=doc.Name,
        exact_vertices=(Point3D(x=20, y=25), Point3D(x=22, y=20), Point3D(x=24, y=25)),
        layer="OUTPUT",
    )
    v_result = live.execute_live_batch26(approved(live.preview_live_v(v_request), v_request))
    assert v_result.created_handles == ("N2",) and not doc.entities[-1].Closed


def test_rs_creates_exact_solid_and_properties(doc: Doc) -> None:
    points = (
        Point3D(x=0, y=0),
        Point3D(x=5, y=0),
        Point3D(x=0, y=3),
        Point3D(x=5, y=3),
    )
    request = SolidRectangleRequest(
        document_id=doc.Name,
        picked_points=(points[0], points[1]),
        exact_solid_vertices=points,
        layer="OUTPUT",
        color_index=3,
    )
    execution = live.execute_live_batch26(approved(live.preview_live_rs(request), request))
    output = doc.entities[-1]
    assert execution.created_handles == ("N1",)
    assert output.Layer == "OUTPUT" and output.Color == 3
    assert output.Coordinates[-3:] == (5, 3, 0)


def test_bad_fingerprint_and_locked_target_are_rejected(doc: Doc) -> None:
    vertices = tuple(item.model_copy(update={"start_width": 1.0, "end_width": 1.0}) for item in snapshot().vertices)
    request = PolylineWidthRequest(
        document_id=doc.Name,
        source=snapshot(),
        exact_result=result(vertices, layer="SOURCE"),
    )
    wrapped = approved(live.preview_live_pw(request), request)
    bad = wrapped.model_copy(update={"approval_fingerprint": "sha256:" + "0" * 64})
    with pytest.raises(ValueError, match="fingerprint"):
        live.execute_live_batch26(bad)
    doc.Layers.items["SOURCE"].Lock = True
    with pytest.raises(ValueError, match="locked"):
        live.preview_live_pw(request)


def test_pj_creates_exact_join_and_erases_only_approved_sources(doc: Doc) -> None:
    first = snapshot()
    doc.entities.append(Polyline("P2", (4, 3, 8, 3)))
    second = first.model_copy(
        update={
            "handle": "P2",
            "geometry_revision": "r2",
            "vertices": (vertex("p2-a", 4, 3), vertex("p2-b", 8, 3)),
        }
    )
    joined = ProposedPolylineResult(
        result_id="joined",
        source_handles=("P1", "P2"),
        entity_type="LWPOLYLINE",
        layer="OUTPUT",
        closed=False,
        vertices=first.vertices + (second.vertices[-1],),
    )
    request = PolylineJoinRequest(
        document_id="Drawing1.dwg",
        sources=(first, second),
        exact_result=joined,
        delete_source_handles=("P1", "P2"),
    )
    preview = live.preview_live_pj(request)
    execution = live.execute_live_batch26(approved(preview, request))
    assert execution.command_alias == "PJ"
    assert execution.created_handles == ("N2",)
    assert execution.erased_handles == ("P1", "P2")
    assert [item.Handle for item in doc.entities if not getattr(item, "deleted", False)] == ["N2"]
    assert doc.marks == ["start", "end"]


def test_registers_twelve_previews_and_eight_execute_tools() -> None:
    class MCP:
        def __init__(self) -> None:
            self.names: list[str] = []

        def tool(self, *, name: str, annotations: Any) -> Any:
            del annotations
            self.names.append(name)
            return lambda function: function

    mcp = MCP()
    live.register_live_batch26_tools(mcp)  # type: ignore[arg-type]
    assert len([name for name in mcp.names if "preview" in name]) == 12
    assert [name for name in mcp.names if "execute" in name] == [
        "xicad_execute_live_pj",
        "xicad_execute_live_pv",
        "xicad_execute_live_pvr",
        "xicad_execute_live_pvv",
        "xicad_execute_live_pw",
        "xicad_execute_live_r3",
        "xicad_execute_live_rs",
        "xicad_execute_live_v",
    ]
