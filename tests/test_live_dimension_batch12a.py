from __future__ import annotations

from types import SimpleNamespace

import pytest

import xicad_mcp.live_dimension_batch12a as live
from xicad_mcp.headless_core_batch1 import Point3D
from xicad_mcp.headless_core_batch11 import DimensionKind, DimensionSnapshot
from xicad_mcp.headless_core_batch12 import (
    DimensionChainMode,
    DimensionScaleScope,
    DimensionStyleEditRequest,
    DimensionStylePatch,
    DimensionTextMoveDirection,
    LinearOrientation,
    PolylineVertexPolicy,
    TextCollisionGroup,
)


class FakeDim:
    def __init__(self, handle: str, object_name: str = "AcDbAlignedDimension") -> None:
        self.Handle, self.ObjectName, self.StyleName = handle, object_name, "A"
        self.Layer, self.TextPosition, self.deleted = "DIM", (5.0, 2.0, 0.0), False

    def Delete(self) -> None:
        self.deleted = True


class FakeStyle:
    def __init__(self, name: str, collection: FakeStyles) -> None:
        self.Name, self.collection, self.deleted = name, collection, False

    def Delete(self) -> None:
        self.deleted = True


class FakeStyles:
    def __init__(self) -> None:
        self.items = {name.casefold(): FakeStyle(name, self) for name in ("A", "B", "Standard")}

    def Item(self, name: str) -> FakeStyle:
        style = self.items[name.casefold()]
        if style.deleted:
            raise KeyError(name)
        return style

    def __iter__(self):
        return (style for style in self.items.values() if not style.deleted)


class FakeModelSpace:
    def __init__(self, adapter: FakeAdapter) -> None:
        self.adapter = adapter

    def _create(self, kind: str) -> FakeDim:
        self.adapter.counter += 1
        entity = FakeDim(f"N{self.adapter.counter}", kind)
        entity.StyleName = "Standard"
        self.adapter.objects[entity.Handle.casefold()] = entity
        return entity

    def AddDimAligned(self, *_args: object) -> FakeDim:
        return self._create("AcDbAlignedDimension")

    def AddDimRotated(self, *_args: object) -> FakeDim:
        return self._create("AcDbRotatedDimension")


class FakeDoc:
    Name = "Drawing1.dwg"

    def __init__(self, adapter: FakeAdapter) -> None:
        self.DimStyles, self.ActiveDimStyle = FakeStyles(), SimpleNamespace(Name="Standard")
        self.ModelSpace, self.started, self.ended = FakeModelSpace(adapter), 0, 0
        self.scale = 1.0

    def GetVariable(self, _name: str) -> float:
        return self.scale

    def SetVariable(self, _name: str, value: float) -> None:
        self.scale = value

    def StartUndoMark(self) -> None:
        self.started += 1

    def EndUndoMark(self) -> None:
        self.ended += 1


class FakeAdapter:
    def __init__(self) -> None:
        self.objects = {"d1": FakeDim("D1"), "d2": FakeDim("D2")}
        self.counter = 0
        self.doc = FakeDoc(self)

    def connect(self) -> FakeDoc:
        return self.doc

    def vector(self, point: Point3D) -> tuple[float, float, float]:
        return (point.x, point.y, point.z)

    def entity_objects(self) -> dict[str, FakeDim]:
        return {handle: entity for handle, entity in self.objects.items() if not entity.deleted}

    def polyline(self, _handle: str):
        from xicad_mcp.headless_core_batch12 import PolylineDimensionSnapshot

        return PolylineDimensionSnapshot(
            handle="P1", vertices=(Point3D(x=0, y=0), Point3D(x=10, y=0), Point3D(x=10, y=5))
        )

    def quick_sources(self, _handles: tuple[str, ...]):
        from xicad_mcp.headless_core_batch12 import QuickDimensionSource

        return (QuickDimensionSource(handle="L1", points=(Point3D(x=0, y=0), Point3D(x=10, y=0), Point3D(x=20, y=0))),)

    def styles(self) -> tuple[live.LiveStyleState, ...]:
        return tuple(
            live.LiveStyleState(
                name=s.Name,
                is_current=s.Name == self.doc.ActiveDimStyle.Name,
            )
            for s in self.doc.DimStyles
        )

    def assignment_dimensions(self) -> tuple[live.LiveDimensionAssignmentState, ...]:
        return tuple(
            live.LiveDimensionAssignmentState(
                handle=e.Handle, style=e.StyleName, layer="DIM", locked_layer=False, is_xref=False, nested=False
            )
            for e in self.entity_objects().values()
        )

    def dimensions(self, handles: tuple[str, ...]) -> tuple[DimensionSnapshot, ...]:
        result = []
        for handle in handles:
            entity = self.objects[handle.casefold()]
            text = Point3D(x=entity.TextPosition[0], y=entity.TextPosition[1], z=0)
            result.append(
                DimensionSnapshot(
                    handle=entity.Handle,
                    kind=DimensionKind.ALIGNED,
                    layer="DIM",
                    style=entity.StyleName,
                    measurement=10,
                    text_position=text,
                    default_text_position=text,
                    dimension_line_point=text,
                    first_extension_origin=Point3D(x=0, y=0),
                    second_extension_origin=Point3D(x=10, y=0),
                    first_extension_length=1,
                    second_extension_length=1,
                    dimscale=1,
                    ltscale=1,
                    object_scale=1,
                )
            )
        return tuple(result)


def install(monkeypatch: pytest.MonkeyPatch, adapter: FakeAdapter) -> None:
    monkeypatch.setattr(live, "ZWCADLiveDimension12aAdapter", lambda _name: adapter)


def test_dpl_creates_dimensions(monkeypatch: pytest.MonkeyPatch) -> None:
    adapter = FakeAdapter()
    install(monkeypatch, adapter)
    p0 = live.LiveDplPreviewRequest(
        document_name="Drawing1.dwg",
        source_handle="P1",
        vertex_policy=PolylineVertexPolicy.CONSECUTIVE_SEGMENTS,
        orientation=LinearOrientation.ALIGNED,
        dimension_line_point=Point3D(x=0, y=8),
        style="Standard",
    )
    p = live.preview_live_dpl(p0)
    r = live.LiveDplExecuteRequest(
        **p0.model_dump(), expected_source=p["expected_source"], approval_fingerprint=p["approval_fingerprint"]
    )
    assert len(live.execute_live_dpl(r).created_handles) == 2


def test_dq_creates_chain(monkeypatch: pytest.MonkeyPatch) -> None:
    adapter = FakeAdapter()
    install(monkeypatch, adapter)
    p0 = live.LiveDqPreviewRequest(
        document_name="Drawing1.dwg",
        source_handles=("L1",),
        chain_mode=DimensionChainMode.CHAIN,
        orientation=LinearOrientation.HORIZONTAL,
        dimension_line_point=Point3D(x=0, y=4),
        style="Standard",
    )
    p = live.preview_live_dq(p0)
    r = live.LiveDqExecuteRequest(
        **p0.model_dump(), expected_sources=p["expected_sources"], approval_fingerprint=p["approval_fingerprint"]
    )
    assert len(live.execute_live_dq(r).created_handles) == 2


def test_dsc_current_style(monkeypatch: pytest.MonkeyPatch) -> None:
    adapter = FakeAdapter()
    install(monkeypatch, adapter)
    p0 = live.LiveDscPreviewRequest(
        document_name="Drawing1.dwg", scope=DimensionScaleScope.CURRENT_STYLE, scale=2, current_style="Standard"
    )
    p = live.preview_live_dsc(p0)
    r = live.LiveDscExecuteRequest(
        **p0.model_dump(),
        expected_style=p["expected_style"],
        expected_scale=p["expected_scale"],
        approval_fingerprint=p["approval_fingerprint"],
    )
    live.execute_live_dsc(r)
    assert adapter.doc.scale == 2


def test_dse_truthful_capability_block() -> None:
    request = live.LiveDsePreviewRequest(
        document_name="Drawing1.dwg",
        request=DimensionStyleEditRequest(
            document_id="Drawing1.dwg", target_style="A", patch=DimensionStylePatch(dimscale=2)
        ),
    )
    with pytest.raises(RuntimeError, match="unavailable"):
        live.preview_live_dse(request)


def test_dsm_merges_style(monkeypatch: pytest.MonkeyPatch) -> None:
    adapter = FakeAdapter()
    install(monkeypatch, adapter)
    p0 = live.LiveDsmPreviewRequest(document_name="Drawing1.dwg", source_styles=("A",), target_style="B")
    p = live.preview_live_dsm(p0)
    r = live.LiveDsmExecuteRequest(
        **p0.model_dump(),
        expected_styles=p["expected_styles"],
        expected_dimensions=p["expected_dimensions"],
        approval_fingerprint=p["approval_fingerprint"],
    )
    result = live.execute_live_dsm(r)
    assert result.changed_handles == ("D1", "D2")


def test_dtm_moves_colliding_text(monkeypatch: pytest.MonkeyPatch) -> None:
    adapter = FakeAdapter()
    install(monkeypatch, adapter)
    p0 = live.LiveDtmPreviewRequest(
        document_name="Drawing1.dwg",
        collision_groups=(TextCollisionGroup(handles=("D1", "D2")),),
        direction=DimensionTextMoveDirection.SIDE,
        offset_factor=3,
        unit_direction=Point3D(x=1, y=0, z=0),
    )
    p = live.preview_live_dtm(p0)
    r = live.LiveDtmExecuteRequest(
        **p0.model_dump(), expected_dimensions=p["expected_dimensions"], approval_fingerprint=p["approval_fingerprint"]
    )
    live.execute_live_dtm(r)
    assert adapter.objects["d2"].TextPosition == (8.0, 2.0, 0.0)
