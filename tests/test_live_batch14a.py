from __future__ import annotations

import pytest

import xicad_mcp.live_batch14a as live
from xicad_mcp.headless_core_batch1 import Point3D
from xicad_mcp.headless_core_batch14 import ExplodePolicy, GeometrySnapshot, SourceDisposition


class Entity:
    def __init__(self, handle: str, start: Point3D, end: Point3D, layer: str = "A") -> None:
        self.Handle, self.Layer, self.ObjectName = handle, layer, "AcDbLine"
        self.StartPoint = (start.x, start.y, start.z)
        self.EndPoint = (end.x, end.y, end.z)
        self.deleted = False

    def Delete(self) -> None:
        self.deleted = True


class Doc:
    Name = "Drawing1.dwg"

    def __init__(self) -> None:
        self.started = self.ended = 0

    def StartUndoMark(self) -> None:
        self.started += 1

    def EndUndoMark(self) -> None:
        self.ended += 1


class Adapter:
    def __init__(self) -> None:
        self.doc = Doc()
        self.counter = 0
        self.states = {
            "p1": GeometrySnapshot(
                handle="P1",
                entity_type="AcDbPolyline",
                vertices=(Point3D(x=0, y=0), Point3D(x=2, y=0), Point3D(x=2, y=2)),
                layer="A",
            )
        }
        self.objects: dict[str, Entity] = {}

    def connect(self) -> Doc:
        return self.doc

    def validate_output_layer(self, name: str) -> None:
        if name != "A":
            raise ValueError("output layer not found")

    def geometry(self, handles: tuple[str, ...]) -> tuple[GeometrySnapshot, ...]:
        return tuple(self.states[handle.casefold()] for handle in handles)

    def entity_objects(self) -> dict[str, Entity]:
        source = Entity("P1", Point3D(x=0, y=0), Point3D(x=2, y=2))
        source.deleted = getattr(self, "source_deleted", False)
        result = {"p1": source, **self.objects}
        return {key: value for key, value in result.items() if not value.deleted}

    def line(self, start: Point3D, end: Point3D, layer: str) -> Entity:
        self.counter += 1
        entity = Entity(f"N{self.counter}", start, end, layer)
        self.objects[entity.Handle.casefold()] = entity
        return entity

    @staticmethod
    def point(value) -> Point3D:
        return Point3D(x=value[0], y=value[1], z=value[2])


def install(monkeypatch, adapter: Adapter) -> None:
    monkeypatch.setattr(live, "ZWCADLiveBatch14aAdapter", lambda _name: adapter)


def test_k_preview_execute(monkeypatch) -> None:
    adapter = Adapter()
    install(monkeypatch, adapter)
    preview_request = live.LiveKPreviewRequest(
        document_name="Drawing1.dwg", insertion_points=(Point3D(x=10, y=20),), size=2, layer="A"
    )
    preview = live.preview_live_k(preview_request)
    execute = live.LiveKExecuteRequest(
        **preview_request.model_dump(), approval_fingerprint=preview["approval_fingerprint"]
    )
    result = live.execute_live_k(execute)
    assert len(result.created_handles) == 3
    assert adapter.doc.started == adapter.doc.ended == 1


def test_lex_is_read_only_and_checks_stale(monkeypatch) -> None:
    adapter = Adapter()
    install(monkeypatch, adapter)
    preview_request = live.LiveLexPreviewRequest(
        document_name="Drawing1.dwg",
        target_handles=("P1",),
        origin=Point3D(x=0, y=0),
        normalize_scale=True,
        include_layer=True,
    )
    preview = live.preview_live_lex(preview_request)
    execute = live.LiveLexExecuteRequest(
        **preview_request.model_dump(),
        expected_geometry=preview["expected_geometry"],
        approval_fingerprint=preview["approval_fingerprint"],
    )
    result = live.execute_live_lex(execute)
    assert len(result.exports) == 1 and adapter.doc.started == 0
    adapter.states["p1"] = adapter.states["p1"].model_copy(update={"layer": "B"})
    with pytest.raises(ValueError, match="changed"):
        live.execute_live_lex(execute)


def test_lxp_preview_execute(monkeypatch) -> None:
    adapter = Adapter()
    install(monkeypatch, adapter)
    preview_request = live.LiveLxpPreviewRequest(
        document_name="Drawing1.dwg",
        target_handles=("P1",),
        policy=ExplodePolicy.LINE_SEGMENTS,
        source_disposition=SourceDisposition.PRESERVE,
        target_layer="A",
    )
    preview = live.preview_live_lxp(preview_request)
    execute = live.LiveLxpExecuteRequest(
        **preview_request.model_dump(),
        expected_geometry=preview["expected_geometry"],
        approval_fingerprint=preview["approval_fingerprint"],
    )
    result = live.execute_live_lxp(execute)
    assert len(result.created_handles) == 2 and result.postcondition_verified


def test_lxp_preserve_arcs_is_blocked(monkeypatch) -> None:
    adapter = Adapter()
    install(monkeypatch, adapter)
    request = live.LiveLxpPreviewRequest(
        document_name="Drawing1.dwg",
        target_handles=("P1",),
        policy=ExplodePolicy.PRESERVE_ARCS,
        source_disposition=SourceDisposition.PRESERVE,
        target_layer="A",
    )
    with pytest.raises(ValueError, match="preserve_arcs"):
        live.preview_live_lxp(request)


def test_fingerprint_tamper_is_rejected(monkeypatch) -> None:
    adapter = Adapter()
    install(monkeypatch, adapter)
    request = live.LiveKExecuteRequest(
        document_name="Drawing1.dwg",
        insertion_points=(Point3D(x=0, y=0),),
        size=1,
        layer="A",
        approval_fingerprint="sha256:" + "0" * 64,
    )
    with pytest.raises(ValueError, match="fingerprint"):
        live.execute_live_k(request)
