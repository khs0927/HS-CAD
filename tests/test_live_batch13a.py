from __future__ import annotations

import pytest

import xicad_mcp.live_batch13a as live
from xicad_mcp.headless_core_batch1 import Point3D
from xicad_mcp.headless_core_batch11 import DimensionKind, DimensionSnapshot
from xicad_mcp.headless_core_batch13 import (
    FlattenPolicy,
    PolylineSnapshot,
    ProjectionPolicy,
    SourceDisposition,
)


class Entity:
    def __init__(self, handle: str, *, layer: str = "A", closed: bool = False, name: str = "AcDbPolyline") -> None:
        self.Handle, self.Layer, self.Closed, self.ObjectName = handle, layer, closed, name
        self.deleted = False
        self.StyleName, self.TextOverride = "Standard", ""

    def Delete(self) -> None:
        self.deleted = True


class ModelSpace:
    def __init__(self, adapter: Adapter) -> None:
        self.adapter = adapter

    def AddDimAligned(self, *_args: object) -> Entity:
        return self.adapter.created("AcDbAlignedDimension", "DIM")


class Doc:
    Name = "Drawing1.dwg"

    def __init__(self, adapter: Adapter) -> None:
        self.ModelSpace, self.started, self.ended = ModelSpace(adapter), 0, 0

    def StartUndoMark(self) -> None:
        self.started += 1

    def EndUndoMark(self) -> None:
        self.ended += 1


class Adapter:
    def __init__(self) -> None:
        self.states = {
            "p1": live.LivePolylineState(
                snapshot=PolylineSnapshot(handle="P1", vertices=(Point3D(x=0, y=0), Point3D(x=1, y=0)), layer="A"),
                object_name="AcDbPolyline",
            ),
            "p2": live.LivePolylineState(
                snapshot=PolylineSnapshot(handle="P2", vertices=(Point3D(x=1, y=0), Point3D(x=2, y=0)), layer="A"),
                object_name="AcDbPolyline",
            ),
            "b1": live.LivePolylineState(
                snapshot=PolylineSnapshot(handle="B1", vertices=(Point3D(x=0, y=0), Point3D(x=2, y=0)), layer="A"),
                object_name="AcDbPolyline",
            ),
            "b2": live.LivePolylineState(
                snapshot=PolylineSnapshot(handle="B2", vertices=(Point3D(x=0, y=1), Point3D(x=2, y=1)), layer="A"),
                object_name="AcDbPolyline",
            ),
            "q1": live.LivePolylineState(
                snapshot=PolylineSnapshot(
                    handle="Q1", vertices=(Point3D(x=0, y=0, z=3), Point3D(x=1, y=0, z=4)), layer="A"
                ),
                object_name="AcDb3dPolyline",
            ),
        }
        self.objects = {
            key: Entity(state.snapshot.handle, name=state.object_name) for key, state in self.states.items()
        }
        self.objects["d1"] = Entity("D1", layer="DIM", name="AcDbAlignedDimension")
        self.counter = 0
        self.doc = Doc(self)

    def connect(self) -> Doc:
        return self.doc

    def vector(self, p: Point3D):
        return (p.x, p.y, p.z)

    def entity_objects(self):
        return {k: v for k, v in self.objects.items() if not v.deleted}

    def polylines(self, handles: tuple[str, ...]):
        return tuple(self.states[h.casefold()] for h in handles)

    def validate_output_layer(self, name: str) -> None:
        if name != "A":
            raise ValueError("output layer not found")

    def created(self, name: str, layer: str) -> Entity:
        self.counter += 1
        e = Entity(f"N{self.counter}", layer=layer, name=name)
        self.objects[e.Handle.casefold()] = e
        return e

    def lwpolyline(self, vertices, closed, layer):
        e = self.created("AcDbPolyline", layer)
        e.Closed = closed
        self.states[e.Handle.casefold()] = live.LivePolylineState(
            snapshot=PolylineSnapshot(handle=e.Handle, vertices=vertices, closed=closed, layer=layer),
            object_name=e.ObjectName,
        )
        return e

    def dimensions(self, _handles, _points):
        z = Point3D(x=0, y=0)
        end = Point3D(x=10, y=0)
        text = Point3D(x=5, y=2)
        return (
            DimensionSnapshot(
                handle="D1",
                kind=DimensionKind.ALIGNED,
                layer="DIM",
                style="Standard",
                measurement=10,
                text_position=text,
                default_text_position=text,
                dimension_line_point=text,
                first_extension_origin=z,
                second_extension_origin=end,
                first_extension_length=1,
                second_extension_length=1,
                dimscale=1,
                ltscale=1,
                object_scale=1,
            ),
        )


def install(monkeypatch, adapter):
    monkeypatch.setattr(live, "ZWCADLiveBatch13aAdapter", lambda _name: adapter)


def test_lx_tl_are_truthfully_blocked():
    with pytest.raises(RuntimeError):
        live.preview_live_lx(live.LiveLxPreviewRequest(document_name="Drawing1.dwg", request={}))
    with pytest.raises(RuntimeError):
        live.preview_live_tl(live.LiveTlPreviewRequest(document_name="Drawing1.dwg", request={}))


def test_sd(monkeypatch):
    a = Adapter()
    install(monkeypatch, a)
    p0 = live.LiveSdPreviewRequest(
        document_name="Drawing1.dwg",
        source_handle="D1",
        split_points=(Point3D(x=5, y=0),),
        dimension_line_point=Point3D(x=5, y=2),
        source_disposition=SourceDisposition.PRESERVE,
    )
    p = live.preview_live_sd(p0)
    r = live.LiveSdExecuteRequest(
        **p0.model_dump(), expected_source=p["expected_source"], approval_fingerprint=p["approval_fingerprint"]
    )
    assert len(live.execute_live_sd(r).created_handles) == 2


def test_2dp(monkeypatch):
    a = Adapter()
    install(monkeypatch, a)
    matrix = ((1, 0, 0, 10), (0, 1, 0, 0), (0, 0, 1, 0), (0, 0, 0, 1))
    p0 = live.Live2dpPreviewRequest(
        document_name="Drawing1.dwg",
        source_handles=("P1",),
        source_boundary_handle="B1",
        target_boundary_handle="B2",
        policy=ProjectionPolicy.AFFINE_MATRIX,
        affine_matrix_4x4=matrix,
        target_layer="A",
        source_disposition=SourceDisposition.PRESERVE,
    )
    p = live.preview_live_2dp(p0)
    r = live.Live2dpExecuteRequest(
        **p0.model_dump(), expected_geometry=p["expected_geometry"], approval_fingerprint=p["approval_fingerprint"]
    )
    assert len(live.execute_live_2dp(r).created_handles) == 1


def test_3tp(monkeypatch):
    a = Adapter()
    install(monkeypatch, a)
    p0 = live.Live3tpPreviewRequest(
        document_name="Drawing1.dwg",
        target_handles=("Q1",),
        flatten_policy=FlattenPolicy.DROP_Z,
        source_disposition=SourceDisposition.PRESERVE,
    )
    p = live.preview_live_3tp(p0)
    r = live.Live3tpExecuteRequest(
        **p0.model_dump(), expected_geometry=p["expected_geometry"], approval_fingerprint=p["approval_fingerprint"]
    )
    assert len(live.execute_live_3tp(r).created_handles) == 1


def test_boo(monkeypatch):
    a = Adapter()
    install(monkeypatch, a)
    p0 = live.LiveBooPreviewRequest(
        document_name="Drawing1.dwg",
        ordered_handles=("P1", "P2"),
        tolerance=0,
        target_layer="A",
        source_disposition=SourceDisposition.REPLACE,
    )
    p = live.preview_live_boo(p0)
    r = live.LiveBooExecuteRequest(
        **p0.model_dump(), expected_geometry=p["expected_geometry"], approval_fingerprint=p["approval_fingerprint"]
    )
    result = live.execute_live_boo(r)
    assert len(result.created_handles) == 1 and result.erased_handles == ("P1", "P2")


def test_2dp_rejects_missing_output_layer(monkeypatch):
    a = Adapter()
    install(monkeypatch, a)
    request = live.Live2dpPreviewRequest(
        document_name="Drawing1.dwg",
        source_handles=("P1",),
        source_boundary_handle="B1",
        target_boundary_handle="B2",
        policy=ProjectionPolicy.AFFINE_MATRIX,
        affine_matrix_4x4=((1, 0, 0, 0), (0, 1, 0, 0), (0, 0, 1, 0), (0, 0, 0, 1)),
        target_layer="MISSING",
        source_disposition=SourceDisposition.PRESERVE,
    )
    with pytest.raises(ValueError, match="output layer"):
        live.preview_live_2dp(request)
