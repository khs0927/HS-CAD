from __future__ import annotations

from typing import Any

import pytest

from xicad_mcp import live_batch25 as live
from xicad_mcp.headless_core_batch1 import Point3D
from xicad_mcp.headless_core_batch25a import (
    CommonTextRequest,
    EnergyAreaTableRequest,
    ExactGraphic,
    ExactGraphicKind,
    NumberedPlacement,
    NumericTextSnapshot,
    TextPointIncrementRequest,
)
from xicad_mcp.headless_core_batch25b import (
    BoundingBoxRequest,
    CurveTangentSnapshot,
    EntityExtentsSnapshot,
    OpenPolylineSnapshot,
    PerpendicularCurveRequest,
    PolylineCloseRequest,
)


class Layer:
    def __init__(self, name: str, locked: bool = False) -> None:
        self.Name, self.Lock = name, locked


class Layers:
    def __init__(self) -> None:
        self.items = {name: Layer(name) for name in ("SOURCE", "ANNO")}

    def Item(self, name: str) -> Layer:
        return self.items[name]


class Entity:
    ObjectName = "AcDbLine"

    def __init__(
        self,
        handle: str,
        minimum: tuple[float, float, float] = (0, 0, 0),
        maximum: tuple[float, float, float] = (4, 3, 0),
    ) -> None:
        self.Handle, self.Layer = handle, "SOURCE"
        self.StartPoint, self.EndPoint = minimum, maximum
        self._bounds = (minimum, maximum)

    def GetBoundingBox(self) -> tuple[tuple[float, float, float], tuple[float, float, float]]:
        return self._bounds


class Polyline(Entity):
    ObjectName = "AcDbPolyline"

    def __init__(self, handle: str, coordinates: tuple[float, ...] = (0, 0, 4, 0, 4, 3)) -> None:
        super().__init__(handle)
        self.Coordinates, self.Closed = coordinates, False


class Text(Entity):
    ObjectName = "AcDbText"

    def __init__(
        self, handle: str, text: str, point: tuple[float, float, float] = (0, 0, 0), height: float = 2.5
    ) -> None:
        super().__init__(handle)
        self.TextString, self.InsertionPoint, self.Height = text, point, height
        self.Rotation = 0.0


class ModelSpace:
    def __init__(self, doc: Doc) -> None:
        self.doc = doc

    def AddText(self, text: str, point: tuple[float, float, float], height: float) -> Text:
        entity = Text(f"N{len(self.doc.entities)}", text, point, height)
        self.doc.entities.append(entity)
        return entity

    def AddLightWeightPolyline(self, coordinates: tuple[float, ...]) -> Polyline:
        entity = Polyline(f"N{len(self.doc.entities)}", coordinates)
        self.doc.entities.append(entity)
        return entity

    def AddLine(self, start: tuple[float, float, float], end: tuple[float, float, float]) -> Entity:
        entity = Entity(f"N{len(self.doc.entities)}", start, end)
        self.doc.entities.append(entity)
        return entity


class Doc:
    Name = "Drawing1.dwg"

    def __init__(self) -> None:
        self.Layers = Layers()
        self.entities: list[Any] = [
            Text("T1", "A009"),
            Polyline("P1"),
            Entity("E1", (1, 2, 0), (5, 7, 0)),
        ]
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
    monkeypatch.setattr(
        live, "_coordinates", lambda points: tuple(value for point in points for value in (point.x, point.y))
    )
    return drawing


def approved(preview: dict[str, Any], request: Any) -> live.LiveBatch25ExecuteRequest:
    return live.LiveBatch25ExecuteRequest(
        request=request,
        expected_sources=tuple(live.LiveEntityEvidence.model_validate(item) for item in preview["expected_sources"]),
        expected_target_layers=tuple(
            live.LiveLayerEvidence.model_validate(item) for item in preview["expected_target_layers"]
        ),
        approval_fingerprint=preview["approval_fingerprint"],
    )


def test_qt_creates_exact_text_with_undo_and_postcondition(doc: Doc) -> None:
    request = CommonTextRequest(
        document_id=doc.Name,
        catalog_group=2,
        catalog_index=4,
        catalog_text="ROOM",
        insertion_point=Point3D(x=10, y=20),
        layer="ANNO",
        text_height=5,
        rotation_degrees=30,
    )
    preview = live.preview_live_qt(request)
    result = live.execute_live_batch25(approved(preview, request))
    output = doc.entities[-1]
    assert result.command_alias == "QT" and result.created_handles == (output.Handle,)
    assert output.TextString == "ROOM" and output.InsertionPoint == (10, 20, 0)
    assert output.Height == 5 and output.Layer == "ANNO"
    assert doc.marks == ["start", "end"] and result.postcondition_verified


def test_tip_stale_checks_numeric_source_and_creates_sequence(doc: Doc) -> None:
    request = TextPointIncrementRequest(
        document_id=doc.Name,
        source=NumericTextSnapshot(source_handle="T1", prefix="A", value=9, minimum_digits=3),
        increment=2,
        placements=(
            NumberedPlacement(insertion_point=Point3D(x=1, y=1), layer="ANNO", text_height=3),
            NumberedPlacement(insertion_point=Point3D(x=2, y=2), layer="ANNO", text_height=3),
        ),
    )
    preview = live.preview_live_tip(request)
    wrapped = approved(preview, request)
    doc.entities[0].TextString = "STALE"
    with pytest.raises(ValueError, match="source state no longer matches"):
        live.execute_live_batch25(wrapped)
    doc.entities[0].TextString = "A009"
    result = live.execute_live_batch25(wrapped)
    assert result.created_handles == ("N3", "N4")
    assert [item.TextString for item in doc.entities[-2:]] == ["A011", "A013"]


def test_pbb_creates_exact_closed_polyline_and_rejects_wrong_extents(doc: Doc) -> None:
    request = BoundingBoxRequest(
        document_id=doc.Name,
        entities=(
            EntityExtentsSnapshot(
                handle="E1",
                minimum=Point3D(x=1, y=2),
                maximum=Point3D(x=5, y=7),
                coordinate_system_id="WCS",
                geometry_revision="r1",
            ),
        ),
        output_layer="ANNO",
    )
    preview = live.preview_live_pbb(request)
    result = live.execute_live_batch25(approved(preview, request))
    output = doc.entities[-1]
    assert result.command_alias == "PBB" and output.Closed
    assert output.Coordinates == (1, 2, 5, 2, 5, 7, 1, 7) and output.Layer == "ANNO"
    wrong = request.model_copy(
        update={"entities": (request.entities[0].model_copy(update={"maximum": Point3D(x=6, y=7)}),)}
    )
    with pytest.raises(ValueError, match="extents do not match"):
        live.preview_live_pbb(wrong)


def test_pc_closes_only_approved_open_polyline(doc: Doc) -> None:
    request = PolylineCloseRequest(
        document_id=doc.Name,
        polylines=(
            OpenPolylineSnapshot(
                handle="P1",
                entity_type="POLYLINE",
                vertices=(Point3D(x=0, y=0), Point3D(x=4, y=0), Point3D(x=4, y=3)),
                geometry_revision="r1",
            ),
        ),
    )
    preview = live.preview_live_pc(request)
    result = live.execute_live_batch25(approved(preview, request))
    assert result.changed_handles == ("P1",) and doc.entities[1].Closed
    assert result.postcondition_verified


def test_pec_creates_exact_perpendicular_line(doc: Doc) -> None:
    request = PerpendicularCurveRequest(
        document_id=doc.Name,
        curves=(
            CurveTangentSnapshot(
                handle="E1", base_point=Point3D(x=3, y=4), tangent_x=1, tangent_y=0, geometry_revision="r1"
            ),
        ),
        negative_length=2,
        positive_length=5,
        output_layer="ANNO",
    )
    preview = live.preview_live_pec(request)
    result = live.execute_live_batch25(approved(preview, request))
    output = doc.entities[-1]
    assert result.created_handles == (output.Handle,)
    assert output.StartPoint == (3, 2, 0) and output.EndPoint == (3, 9, 0)


def test_bad_fingerprint_and_locked_layer_are_rejected(doc: Doc) -> None:
    request = CommonTextRequest(
        document_id=doc.Name,
        catalog_group=1,
        catalog_index=0,
        catalog_text="X",
        insertion_point=Point3D(x=0, y=0),
        layer="ANNO",
        text_height=2,
    )
    wrapped = approved(live.preview_live_qt(request), request)
    bad = wrapped.model_copy(update={"approval_fingerprint": "sha256:" + "0" * 64})
    with pytest.raises(ValueError, match="fingerprint"):
        live.execute_live_batch25(bad)
    doc.Layers.items["ANNO"].Lock = True
    with pytest.raises(ValueError, match="locked"):
        live.preview_live_qt(request)


def test_zae_is_preview_only_with_compiled_area_blocker() -> None:
    request = EnergyAreaTableRequest(
        document_id="Drawing1.dwg",
        source_handles=("E1",),
        result_with_legend=True,
        unit_placement="table",
        elevation_table_scale=100,
        plan_table_scale=100,
        exact_graphics=(
            ExactGraphic(kind=ExactGraphicKind.LINE, layer="ANNO", points=(Point3D(x=0, y=0), Point3D(x=1, y=0))),
        ),
    )
    preview = live.preview_live_zae(request)
    assert not preview["mutation"] and not preview["live_executable"]
    assert "area classification" in preview["blocked_reason"]


def test_registers_eleven_previews_and_eight_execute_tools() -> None:
    class MCP:
        def __init__(self) -> None:
            self.names: list[str] = []

        def tool(self, *, name: str, annotations: Any) -> Any:
            del annotations
            self.names.append(name)
            return lambda function: function

    mcp = MCP()
    live.register_live_batch25_tools(mcp)  # type: ignore[arg-type]
    previews = [name for name in mcp.names if "preview" in name]
    executes = [name for name in mcp.names if "execute" in name]
    assert len(previews) == 11 and len(executes) == 8
    assert executes == [
        "xicad_execute_live_sl",
        "xicad_execute_live_qt",
        "xicad_execute_live_qw",
        "xicad_execute_live_tip",
        "xicad_execute_live_too",
        "xicad_execute_live_pbb",
        "xicad_execute_live_pc",
        "xicad_execute_live_pec",
    ]
