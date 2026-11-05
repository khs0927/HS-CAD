from __future__ import annotations

import pytest

import xicad_mcp.live_batch17a as live
from xicad_mcp.headless_core_batch1 import Point3D
from xicad_mcp.headless_core_batch14 import GeometrySnapshot
from xicad_mcp.headless_core_batch17 import (
    ElevatorRequest,
    EscalatorPlanRequest,
    HatchBoundaryRequest,
    HatchPointRequest,
    HeatGridRequest,
    InsulationMode,
    InsulationRequest,
)


class Entity:
    def __init__(self, handle: str) -> None:
        self.Handle = handle


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
        self.doc, self.counter, self.objects, self.states = Doc(), 0, {}, {}

    def connect(self):
        return self.doc

    def validate_output_layer(self, name):
        if name != "A":
            raise ValueError("layer")

    def _create(self, vertices, closed, layer):
        self.counter += 1
        handle = f"N{self.counter}"
        entity = Entity(handle)
        self.objects[handle.casefold()] = entity
        self.states[handle.casefold()] = GeometrySnapshot(
            handle=handle,
            entity_type="AcDbPolyline" if closed or len(vertices) > 2 else "AcDbLine",
            vertices=vertices,
            closed=closed,
            layer=layer,
        )
        return entity

    def line(self, start, end, layer):
        return self._create((start, end), False, layer)

    def lwpolyline(self, vertices, layer, closed=False):
        return self._create(vertices, closed, layer)

    def entity_objects(self):
        return self.objects

    def geometry(self, handles):
        return tuple(self.states[h.casefold()] for h in handles)


def install(monkeypatch):
    adapter = Adapter()
    monkeypatch.setattr(live, "ZWCADLiveBatch17aAdapter", lambda _name: adapter)
    return adapter


def test_elv_execute(monkeypatch) -> None:
    adapter = install(monkeypatch)
    request = ElevatorRequest(
        document_id="Drawing1.dwg",
        center=Point3D(x=0, y=0),
        shaft_width=10,
        shaft_depth=10,
        car_width=4,
        car_depth=6,
        door_width=2,
        car_count=2,
        shaft_layer="A",
        car_layer="A",
    )
    p0 = live.LiveElvPreviewRequest(document_name="Drawing1.dwg", request=request)
    preview = live.preview_live_elv(p0)
    result = live.execute_live_elv(
        live.LiveElvExecuteRequest(**p0.model_dump(), approval_fingerprint=preview["approval_fingerprint"])
    )
    assert len(result.created_handles) == 5 and adapter.doc.started == adapter.doc.ended == 1


def test_epd_execute(monkeypatch) -> None:
    install(monkeypatch)
    request = EscalatorPlanRequest(
        document_id="Drawing1.dwg",
        start=Point3D(x=0, y=0),
        end=Point3D(x=10, y=0),
        overall_width=4,
        tread_width=2,
        step_pitch=1,
        balustrade_width=0.5,
        layer="A",
    )
    p0 = live.LiveEpdPreviewRequest(document_name="Drawing1.dwg", request=request)
    preview = live.preview_live_epd(p0)
    assert (
        len(
            live.execute_live_epd(
                live.LiveEpdExecuteRequest(**p0.model_dump(), approval_fingerprint=preview["approval_fingerprint"])
            ).created_handles
        )
        == 5
    )


def test_hgrid_execute(monkeypatch) -> None:
    install(monkeypatch)
    request = HeatGridRequest(
        document_id="Drawing1.dwg",
        lower_left=Point3D(x=0, y=0),
        width=10,
        height=8,
        spacing=2,
        edge_offset=1,
        layer="A",
    )
    p0 = live.LiveHgridPreviewRequest(document_name="Drawing1.dwg", request=request)
    preview = live.preview_live_hgrid(p0)
    assert (
        len(
            live.execute_live_hgrid(
                live.LiveHgridExecuteRequest(**p0.model_dump(), approval_fingerprint=preview["approval_fingerprint"])
            ).created_handles
        )
        == 1
    )


def test_hatch_commands_are_blocked() -> None:
    hb = live.LiveHbPreviewRequest(
        document_name="Drawing1.dwg",
        request=HatchBoundaryRequest(document_id="Drawing1.dwg", hatch_handles=("A",), target_layer="A"),
    )
    hp = live.LiveHpPreviewRequest(
        document_name="Drawing1.dwg",
        request=HatchPointRequest(document_id="Drawing1.dwg", hatch_handles=("A",), new_origin=Point3D(x=0, y=0)),
    )
    with pytest.raises(RuntimeError):
        live.preview_live_hb(hb)
    with pytest.raises(RuntimeError):
        live.preview_live_hp(hp)


def test_ins_is_preview_only(monkeypatch) -> None:
    install(monkeypatch)
    request = InsulationRequest(
        document_id="Drawing1.dwg",
        baseline=(Point3D(x=0, y=0), Point3D(x=10, y=0)),
        thickness=2,
        mode=InsulationMode.COMBINED,
        small_threshold=1,
        medium_threshold=3,
        cut_to_length=True,
        remove_end_piece=False,
        layer="A",
    )
    preview = live.preview_live_ins(live.LiveInsPreviewRequest(document_name="Drawing1.dwg", request=request))
    assert preview["plan"]["density_class"] == "medium"
    with pytest.raises(RuntimeError, match="preview-only"):
        live.execute_live_ins(None)
