from __future__ import annotations

from typing import Any

import pytest

from xicad_mcp import live_dimension_batch12b as live
from xicad_mcp.headless_core_batch1 import Point3D
from xicad_mcp.headless_core_batch11 import DimensionKind, DimensionSnapshot
from xicad_mcp.headless_core_batch12 import (
    DimensionSupplementRequest,
    DimensionUpdateRequest,
    EditDimensionScaleRequest,
    EditScaleMode,
    IntersectionLengthRecord,
    IntersectionLengthRequest,
    IntersectionOutput,
    LeaderAlignAxis,
    LeaderAlignRequest,
    LeaderKind,
    LeaderSnapshot,
    LeaderStyleAction,
    LeaderStyleEditRequest,
    SupplementalTextPlacement,
)


class FakeLayer:
    Lock = False


class FakeLayers:
    def Item(self, _name: str) -> FakeLayer:
        return FakeLayer()


class FakeStyle:
    def __init__(self, name: str) -> None:
        self.Name = name


class FakeDimension:
    ObjectName = "AcDbAlignedDimension"
    Layer = "DIM"
    Measurement = 10.0
    ExtLine1Suppress = False
    ExtLine2Suppress = False
    ExtensionLineExtend = 1.0
    LinetypeScale = 1.0

    def __init__(self, handle: str, *, style: str = "OLD", scale: float = 100.0) -> None:
        self.Handle = handle
        self.StyleName = style
        self.ScaleFactor = scale
        self.TextOverride = ""
        self.TextPosition = (5.0, 2.0, 0.0)
        self.ExtLine1Point = (0.0, 0.0, 0.0)
        self.ExtLine2Point = (10.0, 0.0, 0.0)


class FakeLeader:
    ObjectName = "AcDb2dLeader"
    Layer = "DIM"
    StyleName = "STANDARD"

    def __init__(self, handle: str) -> None:
        self.Handle = handle
        self.Coordinates = [0.0, 0.0, 0.0, 5.0, 5.0, 0.0]


class FakeModelSpace:
    def __init__(self, doc: FakeDoc) -> None:
        self.doc = doc

    def AddDimAligned(self, _first: Any, _second: Any, _line: Any) -> FakeDimension:
        entity = FakeDimension(f"N{len(self.doc.entities)}", style="OLD")
        self.doc.entities.append(entity)
        return entity

    def AddText(self, text: str, point: Any, _height: float) -> Any:
        entity = type("FakeText", (), {})()
        entity.Handle = f"T{len(self.doc.entities)}"
        entity.TextString = text
        entity.InsertionPoint = point
        self.doc.entities.append(entity)
        return entity


class FakeDoc:
    Name = "Drawing1.dwg"
    Layers = FakeLayers()
    DimStyles = [FakeStyle("OLD"), FakeStyle("NEW")]

    def __init__(self, entities: list[Any]) -> None:
        self.entities = entities
        self.ModelSpace = FakeModelSpace(self)
        self.marks: list[str] = []

    def StartUndoMark(self) -> None:
        self.marks.append("start")

    def EndUndoMark(self) -> None:
        self.marks.append("end")

    def GetVariable(self, _name: str) -> float:
        return 2.5


def snapshot(entity: FakeDimension) -> DimensionSnapshot:
    point = Point3D(x=5, y=2)
    return DimensionSnapshot(
        handle=entity.Handle,
        kind=DimensionKind.ALIGNED,
        layer="DIM",
        style=entity.StyleName,
        measurement=10,
        text_override=entity.TextOverride,
        text_position=point,
        default_text_position=point,
        dimension_line_point=point,
        first_extension_origin=Point3D(x=0, y=0),
        second_extension_origin=Point3D(x=10, y=0),
        first_extension_suppressed=False,
        second_extension_suppressed=False,
        first_extension_length=1,
        second_extension_length=1,
        dimscale=entity.ScaleFactor,
        ltscale=1,
        object_scale=entity.ScaleFactor,
    )


@pytest.fixture
def doc(monkeypatch: pytest.MonkeyPatch) -> FakeDoc:
    result = FakeDoc([FakeDimension("A"), FakeDimension("B", scale=25), FakeLeader("L")])
    monkeypatch.setattr(live, "_drawing", lambda _name: result)
    monkeypatch.setattr(live, "_layout_objects", lambda _doc: {str(item.Handle).casefold(): item for item in result.entities})
    monkeypatch.setattr(
        live,
        "_snapshots",
        lambda _doc, handles: (
            tuple(snapshot(next(item for item in result.entities if item.Handle.casefold() == handle.casefold())) for handle in handles),
            {
                handle.casefold(): next(item for item in result.entities if item.Handle.casefold() == handle.casefold())
                for handle in handles
            },
        ),
    )
    monkeypatch.setattr(live, "_variant", lambda point: (point.x, point.y, point.z))
    monkeypatch.setattr(live, "_coordinate_variant", lambda values: values)
    return result


def wrap(alias: str, request: Any, dimensions: tuple[DimensionSnapshot, ...]) -> live.LiveDimensionBatch12bExecuteRequest:
    payload = live._dimension_payload(alias, request, dimensions)
    return live.LiveDimensionBatch12bExecuteRequest(
        request=request,
        expected_dimensions=dimensions,
        approval_fingerprint=live._fingerprint(payload),
    )


def test_dto_preview_and_execute_exact_override(doc: FakeDoc) -> None:
    request = DimensionSupplementRequest(
        document_id=doc.Name,
        target_handles=("A",),
        text="NOTE",
        placement=SupplementalTextPlacement.ABOVE,
    )
    preview = live.preview_live_dto(request)
    expected = tuple(DimensionSnapshot.model_validate(item) for item in preview["expected_dimensions"])
    result = live.execute_live_dto(wrap("DTO", request, expected))
    assert doc.entities[0].TextOverride == "NOTE\\X<>"
    assert result.postcondition_verified
    assert doc.marks == ["start", "end"]


def test_du_preserves_override_and_position(doc: FakeDoc) -> None:
    dimension = doc.entities[0]
    dimension.TextOverride = "KEEP"
    request = DimensionUpdateRequest(document_id=doc.Name, target_handles=("A",), target_style="NEW")
    preview = live.preview_live_du(request)
    expected = tuple(DimensionSnapshot.model_validate(item) for item in preview["expected_dimensions"])
    live.execute_live_du(wrap("DU", request, expected))
    assert (dimension.StyleName, dimension.TextOverride, dimension.TextPosition) == ("NEW", "KEEP", (5.0, 2.0, 0.0))


def test_ed_match_object_snapshots_match_and_only_changes_target(doc: FakeDoc) -> None:
    request = EditDimensionScaleRequest(
        document_id=doc.Name,
        target_handles=("A",),
        mode=EditScaleMode.MATCH_OBJECT,
        match_handle="B",
    )
    preview = live.preview_live_ed(request)
    assert len(preview["expected_dimensions"]) == 2
    expected = tuple(DimensionSnapshot.model_validate(item) for item in preview["expected_dimensions"])
    live.execute_live_ed(wrap("ED", request, expected))
    assert (doc.entities[0].ScaleFactor, doc.entities[1].ScaleFactor) == (25, 25)


def test_stale_dimension_snapshot_is_rejected(doc: FakeDoc) -> None:
    request = DimensionSupplementRequest(
        document_id=doc.Name,
        target_handles=("A",),
        text="X",
        placement=SupplementalTextPlacement.SUFFIX,
    )
    expected = (snapshot(doc.entities[0]),)
    wrapped = wrap("DTO", request, expected)
    doc.entities[0].ScaleFactor = 50
    with pytest.raises(ValueError, match="no longer matches"):
        live.execute_live_dto(wrapped)


def test_il_return_only_is_cad_free() -> None:
    request = IntersectionLengthRequest(
        document_id="does-not-need-cad",
        records=(
            IntersectionLengthRecord(
                source_handle="S",
                first_intersection=Point3D(x=0, y=0),
                second_intersection=Point3D(x=3, y=4),
            ),
        ),
        output=IntersectionOutput.RETURN_ONLY,
    )
    preview = live.preview_live_il(request)
    assert preview["results"][0]["length"] == 5
    assert not preview["mutation"]


def test_il_text_execute_creates_and_verifies_entity(doc: FakeDoc) -> None:
    request = IntersectionLengthRequest(
        document_id=doc.Name,
        records=(IntersectionLengthRecord(source_handle="S", first_intersection=Point3D(x=0, y=0), second_intersection=Point3D(x=3, y=4)),),
        output=IntersectionOutput.TEXT,
        insertion_points=(Point3D(x=1, y=1),),
    )
    payload = live._il_payload(request)
    result = live.execute_live_il(
        live.LiveIlExecuteRequest(request=request, approval_fingerprint=live._fingerprint(payload))
    )
    assert result.created_handles == ("T3",)
    assert doc.entities[-1].TextString == "5.00"


def test_lda_classic_leader_preview_and_execute(doc: FakeDoc) -> None:
    request = LeaderAlignRequest(
        document_id=doc.Name,
        target_handles=("L",),
        axis=LeaderAlignAxis.X,
        coordinate=10,
    )
    preview = live.preview_live_lda(request)
    expected = tuple(LeaderSnapshot.model_validate(item) for item in preview["expected_leaders"])
    wrapped = live.LiveLdaExecuteRequest(
        request=request,
        expected_leaders=expected,
        approval_fingerprint=preview["approval_fingerprint"],
    )
    live.execute_live_lda(wrapped)
    assert doc.entities[2].Coordinates[-3:] == [10, 5, 0]


def test_lse_is_explicitly_blocked_without_writable_style_contract() -> None:
    request = LeaderStyleEditRequest(
        document_id="Drawing1.dwg",
        leader_kind=LeaderKind.LEADER,
        action=LeaderStyleAction.RENAME,
        source_style="OLD",
        target_style="NEW",
    )
    with pytest.raises(ValueError, match="writable Leader/MLeader style"):
        live.preview_live_lse(request)


def test_registers_preview_execute_pairs_and_blocked_lse() -> None:
    class MCP:
        def __init__(self) -> None:
            self.names: list[str] = []

        def tool(self, *, name: str, annotations: Any) -> Any:
            del annotations
            self.names.append(name)
            return lambda function: function

    mcp = MCP()
    live.register_live_dimension_batch12b_tools(mcp)  # type: ignore[arg-type]
    assert len(mcp.names) == 11
    assert "xicad_execute_live_lse" not in mcp.names
