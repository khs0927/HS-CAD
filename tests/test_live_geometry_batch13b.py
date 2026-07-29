from __future__ import annotations

from typing import Any

import pytest

from xicad_mcp import live_geometry_batch13b as live
from xicad_mcp.headless_core_batch1 import Point3D
from xicad_mcp.headless_core_batch13 import (
    BreakSymbolKind,
    BreakSymbolRequest,
    CloudStyle,
    CloudWidthRequest,
    ContourJoinEnd,
    ContourJoinRequest,
    DirectionLineRequest,
    DirectionOperation,
    JumpLineRequest,
    JumpRepresentation,
    JumpSide,
    RevisionCloudRequest,
    SourceDisposition,
    WidthSide,
)


class FakeLayer:
    Lock = False


class FakeLayers:
    def Item(self, _name: str) -> FakeLayer:
        return FakeLayer()


class FakePolyline:
    ObjectName = "AcDbPolyline"
    Closed = False
    ConstantWidth = 0.0
    Elevation = 0.0
    Layer = "G"

    def __init__(self, doc: FakeDoc, handle: str, coordinates: list[float], *, bulges: tuple[float, ...] = ()) -> None:
        self.doc = doc
        self.Handle = handle
        self.Coordinates = coordinates
        self.bulges = bulges or (0.0,) * (len(coordinates) // 2)

    def GetBulge(self, index: int) -> float:
        return self.bulges[index]

    def Delete(self) -> None:
        self.doc.entities.remove(self)


class FakeModelSpace:
    def __init__(self, doc: FakeDoc) -> None:
        self.doc = doc

    def AddLightWeightPolyline(self, coordinates: list[float]) -> FakePolyline:
        entity = FakePolyline(self.doc, f"N{len(self.doc.entities)}", list(coordinates))
        self.doc.entities.append(entity)
        return entity


class FakeDoc:
    Name = "Drawing1.dwg"
    Layers = FakeLayers()

    def __init__(self) -> None:
        self.entities: list[FakePolyline] = []
        self.ModelSpace = FakeModelSpace(self)
        self.marks: list[str] = []

    def add(self, handle: str, coordinates: list[float], *, bulges: tuple[float, ...] = ()) -> FakePolyline:
        entity = FakePolyline(self, handle, coordinates, bulges=bulges)
        self.entities.append(entity)
        return entity

    def StartUndoMark(self) -> None:
        self.marks.append("start")

    def EndUndoMark(self) -> None:
        self.marks.append("end")


@pytest.fixture
def doc(monkeypatch: pytest.MonkeyPatch) -> FakeDoc:
    drawing = FakeDoc()
    drawing.add("C", [0, 0, 5, 0])
    drawing.add("B", [0, -2, 5, -2])
    drawing.add("D", [0, 0, 2, 0, 4, 1])
    monkeypatch.setattr(live, "_drawing", lambda _name: drawing)
    monkeypatch.setattr(live, "_entities", lambda _doc: {item.Handle.casefold(): item for item in drawing.entities})
    monkeypatch.setattr(
        live,
        "_variant_coordinates",
        lambda points: [coordinate for point in points for coordinate in (point.x, point.y)],
    )
    return drawing


def cbj_request(*, disposition: SourceDisposition = SourceDisposition.PRESERVE) -> ContourJoinRequest:
    return ContourJoinRequest(
        document_id="Drawing1.dwg",
        contour_handle="C",
        boundary_handle="B",
        ends=ContourJoinEnd.BOTH,
        start_boundary_point=Point3D(x=-1, y=0),
        end_boundary_point=Point3D(x=6, y=0),
        source_disposition=disposition,
    )


def test_cbj_preview_fingerprints_contour_and_boundary(doc: FakeDoc) -> None:
    preview = live.preview_live_cbj(cbj_request())
    assert len(preview["expected_polylines"]) == 2
    assert preview["create_count"] == 1
    assert preview["approval_fingerprint"].startswith("sha256:")


def test_cbj_execute_creates_exact_geometry_and_erases_when_requested(doc: FakeDoc) -> None:
    request = cbj_request(disposition=SourceDisposition.REPLACE)
    preview = live.preview_live_cbj(request)
    wrapped = live.LiveCbjExecuteRequest(
        request=request,
        expected_polylines=tuple(live.LivePolylineEvidence.model_validate(item) for item in preview["expected_polylines"]),
        approval_fingerprint=preview["approval_fingerprint"],
    )
    result = live.execute_live_cbj(wrapped)
    assert result.erased_handles == ("C",)
    assert doc.entities[-1].Coordinates == [-1, 0, 0, 0, 5, 0, 6, 0]
    assert doc.marks == ["start", "end"]


def test_drl_reverse_executes_with_stale_state_guard(doc: FakeDoc) -> None:
    request = DirectionLineRequest(
        document_id=doc.Name,
        target_handles=("D",),
        operation=DirectionOperation.REVERSE,
        arrow_size=1,
        layer="G",
    )
    preview = live.preview_live_drl(request)
    wrapped = live.LiveDrlExecuteRequest(
        request=request,
        expected_polylines=tuple(live.LivePolylineEvidence.model_validate(item) for item in preview["expected_polylines"]),
        approval_fingerprint=preview["approval_fingerprint"],
    )
    doc.entities[2].Coordinates[0] = 99
    with pytest.raises(ValueError, match="no longer matches"):
        live.execute_live_drl(wrapped)


def test_drl_reverse_postcondition(doc: FakeDoc) -> None:
    request = DirectionLineRequest(
        document_id=doc.Name,
        target_handles=("D",),
        operation=DirectionOperation.REVERSE,
        arrow_size=1,
        layer="G",
    )
    preview = live.preview_live_drl(request)
    wrapped = live.LiveDrlExecuteRequest(
        request=request,
        expected_polylines=tuple(live.LivePolylineEvidence.model_validate(item) for item in preview["expected_polylines"]),
        approval_fingerprint=preview["approval_fingerprint"],
    )
    result = live.execute_live_drl(wrapped)
    assert doc.entities[2].Coordinates == [4, 1, 2, 0, 0, 0]
    assert result.changed_handles == ("D",)


def test_curved_polylines_are_blocked_without_bulge_contract(doc: FakeDoc) -> None:
    doc.entities[2].bulges = (0.0, 0.5, 0.0)
    request = DirectionLineRequest(
        document_id=doc.Name,
        target_handles=("D",),
        operation=DirectionOperation.REVERSE,
        arrow_size=1,
        layer="G",
    )
    with pytest.raises(ValueError, match="bulge contract"):
        live.preview_live_drl(request)


def test_annotate_and_under_specified_shape_commands_are_explicitly_blocked(doc: FakeDoc) -> None:
    with pytest.raises(ValueError, match="arrow vertices"):
        live.preview_live_drl(
            DirectionLineRequest(
                document_id=doc.Name,
                target_handles=("D",),
                operation=DirectionOperation.ANNOTATE,
                arrow_size=1,
                layer="G",
            )
        )
    blocked: tuple[tuple[Any, str], ...] = (
        (
            BreakSymbolRequest(
                document_id=doc.Name,
                start=Point3D(x=0, y=0),
                end=Point3D(x=1, y=0),
                kind=BreakSymbolKind.ZIGZAG,
                width=1,
                height=1,
                layer="G",
            ),
            "output vertices",
        ),
        (
            RevisionCloudRequest(
                document_id=doc.Name,
                boundary_vertices=(Point3D(x=0, y=0), Point3D(x=1, y=0), Point3D(x=1, y=1)),
                min_arc_length=1,
                max_arc_length=2,
                style=CloudStyle.NORMAL,
                layer="G",
            ),
            "arc segmentation",
        ),
        (
            CloudWidthRequest(
                document_id=doc.Name,
                target_handles=("D",),
                width=1,
                side=WidthSide.BOTH,
                cap_ends=False,
                source_disposition=SourceDisposition.PRESERVE,
            ),
            "not equivalent",
        ),
        (
            JumpLineRequest(
                document_id=doc.Name,
                base_handle="D",
                crossing_points=(Point3D(x=1, y=0),),
                radius=1,
                side=JumpSide.LEFT,
                representation=JumpRepresentation.ARC,
                layer="G",
            ),
            "tangent arc",
        ),
    )
    functions = (live.preview_live_bs, live.preview_live_cm, live.preview_live_cmw, live.preview_live_jul)
    for function, (request, match) in zip(functions, blocked, strict=True):
        with pytest.raises(ValueError, match=match):
            function(request)


def test_bad_fingerprint_rejected_before_mutation(doc: FakeDoc) -> None:
    request = cbj_request()
    preview = live.preview_live_cbj(request)
    wrapped = live.LiveCbjExecuteRequest(
        request=request,
        expected_polylines=tuple(live.LivePolylineEvidence.model_validate(item) for item in preview["expected_polylines"]),
        approval_fingerprint="sha256:" + "0" * 64,
    )
    with pytest.raises(ValueError, match="fingerprint"):
        live.execute_live_cbj(wrapped)


def test_registers_two_live_aliases_and_four_blocked_previews() -> None:
    class MCP:
        def __init__(self) -> None:
            self.names: list[str] = []

        def tool(self, *, name: str, annotations: Any) -> Any:
            del annotations
            self.names.append(name)
            return lambda function: function

    mcp = MCP()
    live.register_live_geometry_batch13b_tools(mcp)  # type: ignore[arg-type]
    assert len(mcp.names) == 8
    assert {"xicad_execute_live_cbj", "xicad_execute_live_drl"} <= set(mcp.names)
