from __future__ import annotations

import xicad_mcp.live_batch16a as live
from xicad_mcp.headless_core_batch1 import Point3D
from xicad_mcp.headless_core_batch14 import GeometrySnapshot
from xicad_mcp.headless_core_batch16 import (
    BlockPatternRequest,
    CalendarRequest,
    CenterMode,
    CenterPolylineRequest,
    ColumnKind,
    ColumnRequest,
    ConcreteShape,
    PatternElement,
    ScheduleRequest,
    TableCell,
)


class Entity:
    def __init__(self, handle: str, name: str, layer: str) -> None:
        self.Handle, self.ObjectName, self.Layer = handle, name, layer


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
        self.doc, self.counter, self.objects = Doc(), 0, {}
        self.states = {
            "p1": GeometrySnapshot(
                handle="P1", entity_type="AcDbPolyline", vertices=(Point3D(x=0, y=0), Point3D(x=1, y=0)), layer="A"
            ),
            "p2": GeometrySnapshot(
                handle="P2", entity_type="AcDbPolyline", vertices=(Point3D(x=0, y=2), Point3D(x=1, y=2)), layer="A"
            ),
        }

    def connect(self):
        return self.doc

    def validate_output_layer(self, name):
        if name != "A":
            raise ValueError("layer")

    def validate_text_style(self, name):
        if name != "Standard":
            raise ValueError("style")

    def geometry(self, handles):
        return tuple(self.states[h.casefold()] for h in handles)

    def _new(self, name, layer):
        self.counter += 1
        entity = Entity(f"N{self.counter}", name, layer)
        self.objects[entity.Handle.casefold()] = entity
        return entity

    def line(self, _start, _end, layer):
        return self._new("AcDbLine", layer)

    def text(self, _value, _point, _height, layer, _style=None):
        return self._new("AcDbText", layer)

    def lwpolyline(self, _vertices, layer, _closed=False):
        return self._new("AcDbPolyline", layer)

    def circle(self, _center, _radius, layer):
        return self._new("AcDbCircle", layer)

    def entity_objects(self):
        return self.objects


def install(monkeypatch):
    adapter = Adapter()
    monkeypatch.setattr(live, "ZWCADLiveBatch16aAdapter", lambda _name: adapter)
    return adapter


def schedule() -> ScheduleRequest:
    return ScheduleRequest(
        document_id="Drawing1.dwg",
        insertion_point=Point3D(x=0, y=0),
        rows=2,
        columns=2,
        row_height=3,
        column_widths=(4, 5),
        cells=(TableCell(row=0, column=0, text="B1"),),
        grid_layer="A",
        text_layer="A",
        text_height=1,
    )


def test_bli_and_cli_execute(monkeypatch) -> None:
    adapter = install(monkeypatch)
    preview_request = live.LiveSchedulePreviewRequest(document_name="Drawing1.dwg", request=schedule())
    fingerprints = []
    for alias in ("BLI", "CLI"):
        preview = live.preview_live_schedule(preview_request, alias)
        fingerprints.append(preview["approval_fingerprint"])
        execute = live.LiveScheduleExecuteRequest(
            **preview_request.model_dump(), command_alias=alias, approval_fingerprint=preview["approval_fingerprint"]
        )
        assert live.execute_live_schedule(execute).created_handles
    assert adapter.doc.started == adapter.doc.ended == 2
    assert fingerprints[0] != fingerprints[1]


def test_bpt_is_definition_only(monkeypatch) -> None:
    adapter = install(monkeypatch)
    request = BlockPatternRequest(
        document_id="Drawing1.dwg",
        pattern_name="P1",
        base_point=Point3D(x=0, y=0),
        elements=(PatternElement(block_name="B", offset=Point3D(x=1, y=2), scale=1),),
    )
    preview_request = live.LiveBptPreviewRequest(document_name="Drawing1.dwg", request=request)
    preview = live.preview_live_bpt(preview_request)
    result = live.execute_live_bpt(
        live.LiveBptExecuteRequest(**preview_request.model_dump(), approval_fingerprint=preview["approval_fingerprint"])
    )
    assert result.structured_output and adapter.doc.started == 0


def test_calendar_execute(monkeypatch) -> None:
    install(monkeypatch)
    request = CalendarRequest(
        document_id="Drawing1.dwg",
        year=2026,
        month=7,
        week_start=0,
        insertion_point=Point3D(x=0, y=0),
        cell_width=10,
        cell_height=8,
        layer="A",
        text_style="Standard",
    )
    p0 = live.LiveCalendarPreviewRequest(document_name="Drawing1.dwg", request=request)
    preview = live.preview_live_calendar(p0)
    assert live.execute_live_calendar(
        live.LiveCalendarExecuteRequest(**p0.model_dump(), approval_fingerprint=preview["approval_fingerprint"])
    ).created_handles


def test_cep_stale_and_execute(monkeypatch) -> None:
    adapter = install(monkeypatch)
    request = CenterPolylineRequest(
        document_id="Drawing1.dwg",
        first_handle="P1",
        second_handle="P2",
        mode=CenterMode.CENTER,
        node_count=2,
        layer="A",
    )
    p0 = live.LiveCepPreviewRequest(document_name="Drawing1.dwg", request=request)
    preview = live.preview_live_cep(p0)
    execute = live.LiveCepExecuteRequest(
        **p0.model_dump(),
        expected_geometry=preview["expected_geometry"],
        approval_fingerprint=preview["approval_fingerprint"],
    )
    assert len(live.execute_live_cep(execute).created_handles) == 1
    adapter.states["p2"] = adapter.states["p2"].model_copy(update={"layer": "B"})
    try:
        live.execute_live_cep(execute)
    except ValueError as exc:
        assert "changed" in str(exc)
    else:
        raise AssertionError("stale CEP must fail")


def test_col_rc_and_src(monkeypatch) -> None:
    install(monkeypatch)
    for kind in (ColumnKind.RC, ColumnKind.SRC):
        kwargs = (
            {}
            if kind is ColumnKind.RC
            else {"steel_width": 4, "steel_depth": 5, "web_thickness": 1, "flange_thickness": 1}
        )
        request = ColumnRequest(
            document_id="Drawing1.dwg",
            insertion_points=(Point3D(x=0, y=0),),
            kind=kind,
            concrete_shape=ConcreteShape.RECTANGLE,
            concrete_width=10,
            concrete_depth=12,
            concrete_layer="A",
            steel_layer="A",
            **kwargs,
        )
        p0 = live.LiveColPreviewRequest(document_name="Drawing1.dwg", request=request)
        preview = live.preview_live_col(p0)
        result = live.execute_live_col(
            live.LiveColExecuteRequest(**p0.model_dump(), approval_fingerprint=preview["approval_fingerprint"])
        )
        assert len(result.created_handles) == (1 if kind is ColumnKind.RC else 2)
