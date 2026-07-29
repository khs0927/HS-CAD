from __future__ import annotations

from typing import Any

import pytest

from xicad_mcp import live_gap_19_20_next as live
from xicad_mcp.headless_core_batch1 import Point3D
from xicad_mcp.headless_core_batch19b import (
    BatPlacementMode,
    BreakAndTextRequest,
    BreakOverRequest,
    BreakTextStation,
    BreakToCurrentRequest,
    TextAngleMode,
)


class Layer:
    def __init__(self, name: str) -> None:
        self.Name, self.Lock = name, False


class Layers:
    def __init__(self) -> None:
        self.items = {name: Layer(name) for name in ("SRC", "CURRENT", "TEXT")}

    def Item(self, name: str) -> Layer:
        return self.items[name]


class Line:
    ObjectName = "AcDbLine"

    def __init__(self, space: Space, handle: str, start: Any, end: Any) -> None:
        self.space = space
        self.Handle, self.StartPoint, self.EndPoint = handle, start, end
        self.Layer, self.Color, self.Linetype, self.Lineweight, self.Thickness = (
            "SRC",
            2,
            "Continuous",
            25,
            0.5,
        )

    def Delete(self) -> None:
        self.space.entities.remove(self)


class Text:
    ObjectName = "AcDbText"

    def __init__(self, space: Space, handle: str, value: str, point: Any, height: float) -> None:
        self.space = space
        self.Handle, self.TextString, self.InsertionPoint, self.Height = handle, value, point, height
        self.Layer, self.Rotation = "0", 0.0

    def Delete(self) -> None:
        self.space.entities.remove(self)


class Space:
    def __init__(self) -> None:
        self.entities: list[Any] = []
        self.serial = 10

    def __iter__(self):
        return iter(self.entities)

    def AddLine(self, start: Any, end: Any) -> Line:
        self.serial += 1
        entity = Line(self, f"N{self.serial}", start, end)
        self.entities.append(entity)
        return entity

    def AddText(self, value: str, point: Any, height: float) -> Text:
        self.serial += 1
        entity = Text(self, f"N{self.serial}", value, point, height)
        self.entities.append(entity)
        return entity


class Doc:
    Name = "Drawing1.dwg"

    def __init__(self) -> None:
        self.ModelSpace, self.Layers = Space(), Layers()
        self.marks: list[str] = []

    def StartUndoMark(self) -> None:
        self.marks.append("start")

    def EndUndoMark(self) -> None:
        self.marks.append("end")


@pytest.fixture
def doc(monkeypatch: pytest.MonkeyPatch) -> Doc:
    drawing = Doc()
    monkeypatch.setattr(live, "_drawing", lambda _name: drawing)
    monkeypatch.setattr(live, "_variant", lambda point: (point.x, point.y, point.z))
    return drawing


def add_line(doc: Doc, handle: str, start: Any, end: Any) -> Line:
    entity = Line(doc.ModelSpace, handle, start, end)
    doc.ModelSpace.entities.append(entity)
    return entity


def test_bb_exactly_splits_line_and_changes_only_middle_layer(doc: Doc) -> None:
    add_line(doc, "A", (0.0, 0.0, 0.0), (10.0, 0.0, 0.0))
    request = BreakToCurrentRequest(
        document_id=doc.Name,
        source_handle="A",
        first_break_point=Point3D(x=2, y=0),
        second_break_point=Point3D(x=8, y=0),
        current_layer="CURRENT",
    )
    preview = live.preview_live_bb(request)
    result = live.execute_live_bb(
        live.LiveBbExecuteRequest(
            request=request,
            expected_source=live.LiveLineEvidence.model_validate(preview["expected_sources"][0]),
            approval_fingerprint=preview["approval_fingerprint"],
        )
    )
    lines = [item for item in doc.ModelSpace if isinstance(item, Line)]
    assert result.erased_handles == ("A",) and result.postcondition_verified
    assert [(line.StartPoint, line.EndPoint, line.Layer) for line in lines] == [
        ((0, 0, 0), (2, 0, 0), "SRC"),
        ((2, 0, 0), (8, 0, 0), "CURRENT"),
        ((8, 0, 0), (10, 0, 0), "SRC"),
    ]
    assert all((line.Color, line.Lineweight, line.Thickness) == (2, 25, 0.5) for line in lines)
    assert doc.marks == ["start", "end"]


def test_bro_verifies_real_intersections_and_breaks_target_only(doc: Doc) -> None:
    add_line(doc, "T", (0.0, 0.0, 0.0), (10.0, 0.0, 0.0))
    add_line(doc, "C1", (3.0, -2.0, 0.0), (3.0, 2.0, 0.0))
    add_line(doc, "C2", (7.0, -2.0, 0.0), (7.0, 2.0, 0.0))
    request = BreakOverRequest(
        document_id=doc.Name,
        target_handle="T",
        cutter_handles=("C1", "C2"),
        intersection_points=(Point3D(x=3, y=0), Point3D(x=7, y=0)),
        gap=2,
    )
    preview = live.preview_live_bro(request)
    result = live.execute_live_bro(
        live.LiveBroExecuteRequest(
            request=request,
            expected_target=live.LiveLineEvidence.model_validate(preview["expected_sources"][0]),
            expected_cutters=tuple(
                live.LiveLineEvidence.model_validate(item) for item in preview["expected_sources"][1:]
            ),
            approval_fingerprint=preview["approval_fingerprint"],
        )
    )
    assert result.erased_handles == ("T",)
    assert {item.Handle for item in doc.ModelSpace if item.Handle in {"C1", "C2"}} == {"C1", "C2"}
    new_lines = [item for item in doc.ModelSpace if item.Handle.startswith("N")]
    assert [
        coordinate for line in new_lines for point in (line.StartPoint, line.EndPoint) for coordinate in point
    ] == pytest.approx([0, 0, 0, 2, 0, 0, 4, 0, 0, 6, 0, 0, 8, 0, 0, 10, 0, 0])


def test_bro_rejects_caller_point_that_is_not_cutter_intersection(doc: Doc) -> None:
    add_line(doc, "T", (0.0, 0.0, 0.0), (10.0, 0.0, 0.0))
    add_line(doc, "C", (3.0, -2.0, 0.0), (3.0, 2.0, 0.0))
    request = BreakOverRequest(
        document_id=doc.Name,
        target_handle="T",
        cutter_handles=("C",),
        intersection_points=(Point3D(x=4, y=0),),
        gap=1,
    )
    with pytest.raises(ValueError, match="does not match"):
        live.preview_live_bro(request)


def test_bat_position_breaks_line_and_inserts_exact_text(doc: Doc) -> None:
    add_line(doc, "A", (0.0, 0.0, 0.0), (10.0, 0.0, 0.0))
    request = BreakAndTextRequest(
        document_id=doc.Name,
        placement_mode=BatPlacementMode.POSITION,
        stations=(
            BreakTextStation(
                source_handle="A",
                break_center=Point3D(x=5, y=0),
                text_point=Point3D(x=5, y=1),
                rotation_degrees=30,
            ),
        ),
        first_at_half_spacing=False,
        break_gap=2,
        angle_mode=TextAngleMode.PARALLEL,
        text="A-100",
        text_height=2.5,
        text_layer="TEXT",
    )
    preview = live.preview_live_bat(request)
    result = live.execute_live_bat(
        live.LiveBatExecuteRequest(
            request=request,
            expected_sources=tuple(live.LiveLineEvidence.model_validate(item) for item in preview["expected_sources"]),
            approval_fingerprint=preview["approval_fingerprint"],
        )
    )
    text = next(item for item in doc.ModelSpace if isinstance(item, Text))
    assert result.command_alias == "BAT" and result.erased_handles == ("A",)
    assert (text.TextString, text.InsertionPoint, text.Height, text.Layer) == (
        "A-100",
        (5, 1, 0),
        2.5,
        "TEXT",
    )
    assert text.Rotation == pytest.approx(0.5235987755982988)


def test_bat_rejects_non_position_mode_and_stale_source(doc: Doc) -> None:
    source = add_line(doc, "A", (0.0, 0.0, 0.0), (10.0, 0.0, 0.0))
    base = BreakAndTextRequest(
        document_id=doc.Name,
        placement_mode=BatPlacementMode.POSITION,
        stations=(
            BreakTextStation(
                source_handle="A",
                break_center=Point3D(x=5, y=0),
                text_point=Point3D(x=5, y=1),
                rotation_degrees=0,
            ),
        ),
        first_at_half_spacing=False,
        break_gap=1,
        angle_mode=TextAngleMode.ZERO,
        text="A",
        text_height=1,
        text_layer="TEXT",
    )
    with pytest.raises(ValueError, match="POSITION"):
        live.preview_live_bat(base.model_copy(update={"placement_mode": BatPlacementMode.MIDDLE}))
    preview = live.preview_live_bat(base)
    wrapped = live.LiveBatExecuteRequest(
        request=base,
        expected_sources=tuple(live.LiveLineEvidence.model_validate(item) for item in preview["expected_sources"]),
        approval_fingerprint=preview["approval_fingerprint"],
    )
    source.EndPoint = (12.0, 0.0, 0.0)
    with pytest.raises(ValueError, match="stale"):
        live.execute_live_bat(wrapped)


def test_failed_postcondition_rolls_back_created_lines_and_restores_source(
    doc: Doc,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    add_line(doc, "A", (0.0, 0.0, 0.0), (10.0, 0.0, 0.0))
    request = BreakToCurrentRequest(
        document_id=doc.Name,
        source_handle="A",
        first_break_point=Point3D(x=2, y=0),
        second_break_point=Point3D(x=8, y=0),
        current_layer="CURRENT",
    )
    preview = live.preview_live_bb(request)
    wrapped = live.LiveBbExecuteRequest(
        request=request,
        expected_source=live.LiveLineEvidence.model_validate(preview["expected_sources"][0]),
        approval_fingerprint=preview["approval_fingerprint"],
    )
    original_entities = live._modelspace_entities
    calls = 0

    def missing_created(drawing: Doc) -> dict[str, Any]:
        nonlocal calls
        calls += 1
        entities = original_entities(drawing)
        if calls == 3:
            return {key: value for key, value in entities.items() if not key.startswith("n")}
        return entities

    monkeypatch.setattr(live, "_modelspace_entities", missing_created)
    with pytest.raises(RuntimeError, match="postcondition"):
        live.execute_live_bb(wrapped)
    remaining = [item for item in doc.ModelSpace if isinstance(item, Line)]
    assert len(remaining) == 1
    assert (remaining[0].StartPoint, remaining[0].EndPoint, remaining[0].Layer) == (
        (0, 0, 0),
        (10, 0, 0),
        "SRC",
    )


def test_registers_three_preview_execute_pairs() -> None:
    class MCP:
        def __init__(self) -> None:
            self.names: list[str] = []

        def tool(self, *, name: str, annotations: Any) -> Any:
            del annotations
            self.names.append(name)
            return lambda function: function

    mcp = MCP()
    live.register_live_gap_19_20_next_tools(mcp)  # type: ignore[arg-type]
    assert mcp.names == [
        "xicad_preview_live_bat_exact",
        "xicad_execute_live_bat_exact",
        "xicad_preview_live_bb_exact",
        "xicad_execute_live_bb_exact",
        "xicad_preview_live_bro_exact",
        "xicad_execute_live_bro_exact",
    ]
