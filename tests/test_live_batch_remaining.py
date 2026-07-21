from __future__ import annotations

from typing import Any

import pytest

from xicad_mcp.headless_core_batch1 import MultiplicationRequest, Point3D
from xicad_mcp.headless_core_batch2 import (
    ExistingStylePolicy,
    SectionMarkMode,
    SectionMarkRequest,
    SectionNormalSide,
    TableStyleSpec,
)
from xicad_mcp.headless_core_batch3 import (
    DoorHinge,
    DoorSwing,
    ToiletBoothLegacyVariant,
    ToiletBoothRequest,
)
from xicad_mcp.live_batch_remaining import (
    LiveSectionMarkExecuteRequest,
    LiveSectionMarkPreviewRequest,
    LiveTableStyleExecuteRequest,
    LiveTableStylePreviewRequest,
    LiveToiletBoothExecuteRequest,
    LiveToiletBoothPreviewRequest,
    execute_cad_free_multiplication,
    execute_live_mtb2,
    execute_live_scc,
    execute_live_scd,
    execute_live_table_style,
    execute_live_toilet_booth,
    preview_live_section_mark,
    preview_live_table_style,
    preview_live_toilet_booth,
)


class FakeNamedCollection:
    def __init__(self, names: tuple[str, ...]) -> None:
        self.items = {name.casefold(): object() for name in names}

    def Item(self, name: str) -> Any:
        try:
            return self.items[name.casefold()]
        except KeyError as exc:
            raise RuntimeError(name) from exc


class FakeEntity:
    def __init__(self, space: FakeModelSpace, handle: str, object_name: str) -> None:
        self.space = space
        self.Handle = handle
        self.ObjectName = object_name
        self.Layer = "0"
        self.StyleName = "Standard"
        self.Rotation = 0.0


class FakeModelSpace:
    def __init__(self) -> None:
        self.entities: list[FakeEntity] = []

    def _add(self, object_name: str) -> FakeEntity:
        entity = FakeEntity(self, f"{len(self.entities) + 1:X}", object_name)
        self.entities.append(entity)
        return entity

    def AddLine(self, _start: Any, _end: Any) -> FakeEntity:
        return self._add("AcDbLine")

    def AddArc(self, _center: Any, _radius: float, _start: float, _end: float) -> FakeEntity:
        return self._add("AcDbArc")

    def AddText(self, _text: str, _point: Any, _height: float) -> FakeEntity:
        return self._add("AcDbText")

    def __iter__(self):
        return iter(self.entities)


class FakeTableStyle:
    def __init__(self) -> None:
        self.text_styles = {1: "Standard", 2: "Standard", 4: "Standard"}
        self.heights = {1: 1.0, 2: 1.0, 4: 1.0}
        self.HorzCellMargin = 0.0
        self.VertCellMargin = 0.0
        self.FlowDirection = 0

    def GetTextStyle(self, row: int) -> str:
        return self.text_styles[row]

    def SetTextStyle(self, row: int, value: str) -> None:
        self.text_styles[row] = value

    def GetTextHeight(self, row: int) -> float:
        return self.heights[row]

    def SetTextHeight(self, row: int, value: float) -> None:
        self.heights[row] = value


class FakeTableDictionary:
    def __init__(self) -> None:
        self.styles: dict[str, FakeTableStyle] = {}

    def Item(self, name: str) -> FakeTableStyle:
        try:
            return self.styles[name.casefold()]
        except KeyError as exc:
            raise RuntimeError(name) from exc

    def AddObject(self, name: str, class_name: str) -> FakeTableStyle:
        assert class_name == "AcDbTableStyle"
        style = FakeTableStyle()
        self.styles[name.casefold()] = style
        return style


class FakeDictionaries:
    def __init__(self, table_styles: FakeTableDictionary) -> None:
        self.table_styles = table_styles

    def Item(self, name: str) -> FakeTableDictionary:
        if name != "ACAD_TABLESTYLE":
            raise RuntimeError(name)
        return self.table_styles


class FakeDocument:
    def __init__(self) -> None:
        self.Name = "Drawing1.dwg"
        self.ModelSpace = FakeModelSpace()
        self.Layers = FakeNamedCollection(("0", "A-TOILET", "A-ANNO"))
        self.TextStyles = FakeNamedCollection(("Standard",))
        self.table_styles = FakeTableDictionary()
        self.Dictionaries = FakeDictionaries(self.table_styles)
        self.events: list[str] = []

    def StartUndoMark(self) -> None:
        self.events.append("start")

    def EndUndoMark(self) -> None:
        self.events.append("end")


def booth() -> ToiletBoothRequest:
    return ToiletBoothRequest(
        document_id="Drawing1.dwg",
        legacy_variant=ToiletBoothLegacyVariant.MTB1,
        origin=Point3D(x=0, y=0),
        direction_degrees=0,
        stall_count=2,
        stall_width=1000,
        stall_depth=1500,
        door_width=600,
        door_clearance_from_side=100,
        door_hinges=(DoorHinge.LEFT, DoorHinge.RIGHT),
        door_swing=DoorSwing.INWARD,
        layer="A-TOILET",
    )


def section(mode: SectionMarkMode = SectionMarkMode.SINGLE) -> SectionMarkRequest:
    return SectionMarkRequest(
        document_id="Drawing1.dwg",
        mode=mode,
        cut_start=Point3D(x=0, y=0),
        cut_end=Point3D(x=1000, y=0),
        normal_side=SectionNormalSide.LEFT,
        label_start="A",
        label_end="A",
        tail_length=200,
        double_line_gap=50 if mode is SectionMarkMode.DOUBLE else None,
        text_offset=100,
        layer="A-ANNO",
        text_style="Standard",
        text_height=100,
    )


def table_spec() -> TableStyleSpec:
    return TableStyleSpec(
        style_name="XI_TB_N",
        title_text_style="Standard",
        header_text_style="Standard",
        data_text_style="Standard",
        title_text_height=5,
        header_text_height=4,
        data_text_height=3,
        horizontal_cell_margin=1,
        vertical_cell_margin=2,
        flow_direction="down",
    )


def test_multiplication_is_promoted_as_cad_free_production_result() -> None:
    result = execute_cad_free_multiplication(
        MultiplicationRequest(operands=("1.25", "8"), decimal_places=2)
    )
    assert str(result.result.result) == "10.00"
    assert result.production_usable is True


def test_mtb_preview_and_execution_create_verified_geometry(monkeypatch: pytest.MonkeyPatch) -> None:
    doc = FakeDocument()
    monkeypatch.setattr("xicad_mcp.live_batch_remaining._drawing", lambda _name: doc)
    monkeypatch.setattr("xicad_mcp.live_batch_remaining._point", lambda point: point)
    preview_request = LiveToiletBoothPreviewRequest(document_name=doc.Name, booth=booth())
    preview = preview_live_toilet_booth(preview_request)
    execution = LiveToiletBoothExecuteRequest(
        **preview_request.model_dump(), approval_fingerprint=preview["approval_fingerprint"]
    )

    result = execute_live_toilet_booth(execution)

    assert result.command_alias == "MTB1"
    assert len(result.created_handles) == 12
    assert all(item.present and item.type_matches for item in result.evidence)
    assert doc.events == ["start", "end"]


def test_mtb_fingerprint_rejects_tampering_before_cad(monkeypatch: pytest.MonkeyPatch) -> None:
    request = LiveToiletBoothExecuteRequest(
        document_name="Drawing1.dwg",
        booth=booth(),
        approval_fingerprint="sha256:" + "0" * 64,
    )
    monkeypatch.setattr(
        "xicad_mcp.live_batch_remaining._drawing",
        lambda _name: pytest.fail("CAD must not be contacted"),
    )
    with pytest.raises(ValueError, match="fingerprint"):
        execute_live_toilet_booth(request)


def test_mtb_specific_executor_rejects_wrong_variant_before_cad(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    preview = LiveToiletBoothPreviewRequest(document_name="Drawing1.dwg", booth=booth())
    request = LiveToiletBoothExecuteRequest(
        **preview.model_dump(), approval_fingerprint=preview.fingerprint()
    )
    monkeypatch.setattr(
        "xicad_mcp.live_batch_remaining._drawing",
        lambda _name: pytest.fail("CAD must not be contacted"),
    )
    with pytest.raises(ValueError, match="only executes MTB2"):
        execute_live_mtb2(request)


@pytest.mark.parametrize("mode", [SectionMarkMode.SINGLE, SectionMarkMode.DOUBLE])
def test_scc_scd_create_lines_and_labels(monkeypatch: pytest.MonkeyPatch, mode: SectionMarkMode) -> None:
    doc = FakeDocument()
    monkeypatch.setattr("xicad_mcp.live_batch_remaining._drawing", lambda _name: doc)
    monkeypatch.setattr("xicad_mcp.live_batch_remaining._point", lambda point: point)
    preview_request = LiveSectionMarkPreviewRequest(document_name=doc.Name, section=section(mode))
    preview = preview_live_section_mark(preview_request)
    execution = LiveSectionMarkExecuteRequest(
        **preview_request.model_dump(), approval_fingerprint=preview["approval_fingerprint"]
    )

    result = execute_live_scc(execution) if mode is SectionMarkMode.SINGLE else execute_live_scd(execution)

    assert result.command_alias == ("SCC" if mode is SectionMarkMode.SINGLE else "SCD")
    assert len(result.created_handles) == (5 if mode is SectionMarkMode.SINGLE else 6)
    assert doc.events == ["start", "end"]


def test_section_specific_executor_rejects_wrong_mode_before_cad(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    preview_request = LiveSectionMarkPreviewRequest(document_name="Drawing1.dwg", section=section())
    execution = LiveSectionMarkExecuteRequest(
        **preview_request.model_dump(), approval_fingerprint=preview_request.fingerprint()
    )
    monkeypatch.setattr(
        "xicad_mcp.live_batch_remaining._drawing",
        lambda _name: pytest.fail("CAD must not be contacted"),
    )
    with pytest.raises(ValueError, match="only executes SCD"):
        execute_live_scd(execution)


def test_tbm_create_is_fingerprinted_and_postcondition_verified(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    doc = FakeDocument()
    monkeypatch.setattr("xicad_mcp.live_batch_remaining._drawing", lambda _name: doc)
    preview_request = LiveTableStylePreviewRequest(
        document_name=doc.Name,
        desired=table_spec(),
        existing_policy=ExistingStylePolicy.ERROR,
    )
    preview = preview_live_table_style(preview_request)
    execution = LiveTableStyleExecuteRequest(
        **preview_request.model_dump(),
        expected_existing=preview["expected_existing"],
        expected_action=preview["expected_action"],
        approval_fingerprint=preview["approval_fingerprint"],
    )

    result = execute_live_table_style(execution)

    assert result.action.value == "create"
    assert result.changed is True
    assert result.postcondition_verified is True
    assert doc.events == ["start", "end"]


def test_tbm_detects_existing_style_drift_before_undo(monkeypatch: pytest.MonkeyPatch) -> None:
    doc = FakeDocument()
    monkeypatch.setattr("xicad_mcp.live_batch_remaining._drawing", lambda _name: doc)
    preview_request = LiveTableStylePreviewRequest(
        document_name=doc.Name,
        desired=table_spec(),
        existing_policy=ExistingStylePolicy.UPDATE,
    )
    preview = preview_live_table_style(preview_request)
    execution = LiveTableStyleExecuteRequest(
        **preview_request.model_dump(),
        expected_existing=preview["expected_existing"],
        expected_action=preview["expected_action"],
        approval_fingerprint=preview["approval_fingerprint"],
    )
    doc.table_styles.AddObject("XI_TB_N", "AcDbTableStyle")

    with pytest.raises(ValueError, match="no longer matches"):
        execute_live_table_style(execution)
    assert doc.events == []
