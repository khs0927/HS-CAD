from __future__ import annotations

from decimal import Decimal

import pytest

import xicad_mcp.live_text_batch8a as live
from xicad_mcp.headless_core_batch1 import Point3D
from xicad_mcp.headless_core_batch5 import DrawingSpace, TextEntityKind, TextEntitySnapshot
from xicad_mcp.headless_core_batch8 import (
    AttributeConversionMode,
    AttributeEditSpec,
    AttributeOperation,
    ComprehensiveTextPatch,
    ContextReplacementPolicy,
    ContextSelectionPrecedence,
    FrameFitMode,
    SourceDisposition,
    TextCopyDestination,
    TextCopyPlacement,
)


def text_snapshot(handle: str, text: str, kind: TextEntityKind = TextEntityKind.TEXT) -> TextEntitySnapshot:
    return TextEntitySnapshot(
        handle=handle,
        text=text,
        kind=kind,
        layer="TEXT",
        text_style="Standard",
        text_height=2.5,
        insertion_point=Point3D(x=1, y=2, z=0),
    )


class FakeEntity:
    def __init__(self, handle: str, text: str, object_name: str = "AcDbText") -> None:
        self.Handle, self.TextString, self.ObjectName = handle, text, object_name
        self.Layer, self.StyleName = "TEXT", "Standard"
        self.Height = self.TextHeight = 2.5
        self.Rotation, self.WidthFactor, self.Width = 0.0, 1.0, 20.0
        self.deleted = False

    def Delete(self) -> None:
        self.deleted = True


class FakeAttribute(FakeEntity):
    def __init__(self, handle: str, tag: str, value: str) -> None:
        super().__init__(handle, value, "AcDbAttribute")
        self.TagString = tag


class FakeBlock(FakeEntity):
    def __init__(self, attribute: FakeAttribute) -> None:
        super().__init__("B1", "", "AcDbBlockReference")
        self.Name, self.HasAttributes = "ROOM_TAG", True
        self.attribute = attribute

    def GetAttributes(self) -> list[FakeAttribute]:
        return [] if self.attribute.deleted else [self.attribute]


class FakeTable(FakeEntity):
    def __init__(self) -> None:
        super().__init__("T1", "", "AcDbTable")
        self.cells = {(0, 0): "OLD"}

    def GetText(self, row: int, column: int) -> str:
        return self.cells[(row, column)]

    def SetText(self, row: int, column: int, text: str) -> None:
        self.cells[(row, column)] = text


class FakeSpace:
    def __init__(self, adapter: FakeAdapter) -> None:
        self.adapter = adapter

    def AddText(self, text: str, _point: object, height: float) -> FakeEntity:
        entity = self.adapter.created(text)
        entity.Height = height
        return entity

    def AddMText(self, _point: object, _width: float, text: str) -> FakeEntity:
        return self.adapter.created(text, "AcDbMText")


class FakeDoc:
    Name = "Drawing1.dwg"

    def __init__(self) -> None:
        self.started = self.ended = 0
        self.Layers = type("Items", (), {"Item": lambda _self, _name: object()})()
        self.TextStyles = type("Items", (), {"Item": lambda _self, _name: object()})()

    def StartUndoMark(self) -> None:
        self.started += 1

    def EndUndoMark(self) -> None:
        self.ended += 1


class FakeAdapter:
    def __init__(self) -> None:
        self.doc = FakeDoc()
        self.attribute = FakeAttribute("A1", "NO", "10")
        self.block = FakeBlock(self.attribute)
        self.table_entity = FakeTable()
        self.entities = {
            "x1": FakeEntity("X1", "ROOM ROOM"),
            "m1": FakeEntity("M1", "PARAGRAPH", "AcDbMText"),
            "t1": self.table_entity,
        }
        self.space = FakeSpace(self)
        self.counter = 0x200

    def connect(self) -> FakeDoc:
        return self.doc

    def vector(self, point: Point3D) -> tuple[float, float, float]:
        return (point.x, point.y, point.z)

    def owner(self, _handle: str) -> FakeSpace:
        return self.space

    def created(self, text: str, object_name: str = "AcDbText") -> FakeEntity:
        self.counter += 1
        entity = FakeEntity(f"{self.counter:X}", text, object_name)
        self.entities[entity.Handle.casefold()] = entity
        return entity

    def objects(self) -> dict[str, FakeEntity]:
        return {handle: entity for handle, entity in self.entities.items() if not entity.deleted}

    def entity(self, handle: str) -> FakeEntity:
        return self.entities[handle.casefold()]

    def snapshots(self, handles: tuple[str, ...]) -> tuple[TextEntitySnapshot, ...]:
        result = []
        for handle in handles:
            entity = self.entity(handle)
            kind = TextEntityKind.MTEXT if entity.ObjectName == "AcDbMText" else TextEntityKind.TEXT
            result.append(
                TextEntitySnapshot(
                    handle=entity.Handle,
                    text=entity.TextString,
                    kind=kind,
                    layer=entity.Layer,
                    text_style=entity.StyleName,
                    text_height=entity.TextHeight if kind is TextEntityKind.MTEXT else entity.Height,
                    insertion_point=Point3D(x=1, y=2, z=0),
                )
            )
        return tuple(result)

    def attributes(self, handles: tuple[str, ...]) -> tuple[object, ...]:
        from xicad_mcp.headless_core_batch8 import AttributeSnapshot

        assert handles == ("A1",)
        return (
            AttributeSnapshot(
                handle="A1",
                owner_block_handle="B1",
                tag="NO",
                value=self.attribute.TextString,
                insertion_point=Point3D(x=1, y=2, z=0),
                layer="TEXT",
                text_style="Standard",
                text_height=2.5,
            ),
        )

    def attribute_entities(self) -> dict[str, FakeAttribute]:
        return {} if self.attribute.deleted else {"a1": self.attribute}

    def blocks(self, handles: tuple[str, ...]) -> tuple[object, ...]:
        from xicad_mcp.headless_core_batch8 import AttributeBlockSnapshot

        assert handles == ("B1",)
        attributes = {} if self.attribute.deleted else {"NO": self.attribute.TextString}
        return (AttributeBlockSnapshot(handle="B1", name="ROOM_TAG", attributes=attributes, space=DrawingSpace.MODEL),)

    def _block_references(self) -> dict[str, tuple[FakeBlock, FakeSpace, bool]]:
        return {"b1": (self.block, self.space, False)}

    def table(self, handle: str) -> FakeTable:
        assert handle == "T1"
        return self.table_entity

    def frames(self, measurements: tuple[live.LiveFrameMeasurement, ...]) -> tuple[object, ...]:
        from xicad_mcp.headless_core_batch8 import MTextFrameSnapshot

        return tuple(
            MTextFrameSnapshot(
                handle=m.handle,
                current_width=self.entity(m.handle).Width,
                measured_content_width=m.measured_content_width,
                text_height=self.entity(m.handle).TextHeight,
            )
            for m in measurements
        )


def install(monkeypatch: pytest.MonkeyPatch, adapter: FakeAdapter) -> None:
    monkeypatch.setattr(live, "ZWCADLiveText8aAdapter", lambda _name: adapter)


def test_a2m_replaces_attribute_with_text(monkeypatch: pytest.MonkeyPatch) -> None:
    adapter = FakeAdapter()
    install(monkeypatch, adapter)
    preview_request = live.LiveA2mPreviewRequest(
        document_name="Drawing1.dwg",
        target_handles=("A1",),
        mode=AttributeConversionMode.ATTRIBUTE_TO_TEXT,
        include_tag=True,
        source_disposition=SourceDisposition.REPLACE,
    )
    preview = live.preview_live_a2m(preview_request)
    request = live.LiveA2mExecuteRequest(
        **preview_request.model_dump(),
        expected_attributes=preview["expected_attributes"],
        approval_fingerprint=preview["approval_fingerprint"],
    )
    result = live.execute_live_a2m(request)
    assert len(result.created_handles) == 1 and result.erased_handles == ("A1",)


def test_abe_numeric_attribute_edit(monkeypatch: pytest.MonkeyPatch) -> None:
    adapter = FakeAdapter()
    install(monkeypatch, adapter)
    preview_request = live.LiveAbePreviewRequest(
        document_name="Drawing1.dwg",
        target_block_handles=("B1",),
        edits=(AttributeEditSpec(tag="NO", operation=AttributeOperation.ADD, value=Decimal("5")),),
        missing_tag_policy="error",
    )
    preview = live.preview_live_abe(preview_request)
    request = live.LiveAbeExecuteRequest(
        **preview_request.model_dump(),
        expected_blocks=preview["expected_blocks"],
        approval_fingerprint=preview["approval_fingerprint"],
    )
    live.execute_live_abe(request)
    assert adapter.attribute.TextString == "15"


def test_ctx_replaces_all_occurrences(monkeypatch: pytest.MonkeyPatch) -> None:
    adapter = FakeAdapter()
    install(monkeypatch, adapter)
    preview_request = live.LiveCtxPreviewRequest(
        document_name="Drawing1.dwg",
        target_handles=("X1",),
        old_text="ROOM",
        new_text="SPACE",
        selection_precedence=ContextSelectionPrecedence.OBJECT_FIRST,
        whole_string_match=False,
        replacement_policy=ContextReplacementPolicy.ALL_OCCURRENCES,
        zoom_text_height_factor=10,
    )
    preview = live.preview_live_ctx(preview_request)
    request = live.LiveCtxExecuteRequest(
        **preview_request.model_dump(),
        expected_entities=preview["expected_entities"],
        approval_fingerprint=preview["approval_fingerprint"],
    )
    live.execute_live_ctx(request)
    assert adapter.entity("X1").TextString == "SPACE SPACE"


def test_tc_creates_text_and_updates_table(monkeypatch: pytest.MonkeyPatch) -> None:
    adapter = FakeAdapter()
    install(monkeypatch, adapter)
    placements = (
        TextCopyPlacement(
            source_handle="X1", destination=TextCopyDestination.NEW_TEXT, insertion_point=Point3D(x=5, y=5, z=0)
        ),
        TextCopyPlacement(
            source_handle="X1",
            destination=TextCopyDestination.TABLE_CELL,
            table_handle="T1",
            row=0,
            column=0,
            expected_cell_text="OLD",
        ),
    )
    preview_request = live.LiveTcPreviewRequest(document_name="Drawing1.dwg", placements=placements)
    preview = live.preview_live_tc(preview_request)
    request = live.LiveTcExecuteRequest(
        **preview_request.model_dump(),
        expected_entities=preview["expected_entities"],
        expected_cells=preview["expected_cells"],
        approval_fingerprint=preview["approval_fingerprint"],
    )
    result = live.execute_live_tc(request)
    assert len(result.created_handles) == 1 and adapter.table_entity.GetText(0, 0) == "ROOM ROOM"


def test_te_applies_explicit_property_patch(monkeypatch: pytest.MonkeyPatch) -> None:
    adapter = FakeAdapter()
    install(monkeypatch, adapter)
    preview_request = live.LiveTePreviewRequest(
        document_name="Drawing1.dwg",
        patches=(
            ComprehensiveTextPatch(
                handle="X1", expected_text="ROOM ROOM", replacement_text="DONE", target_layer="NOTES", text_height=4
            ),
        ),
    )
    preview = live.preview_live_te(preview_request)
    request = live.LiveTeExecuteRequest(
        **preview_request.model_dump(),
        expected_entities=preview["expected_entities"],
        approval_fingerprint=preview["approval_fingerprint"],
    )
    live.execute_live_te(request)
    assert (adapter.entity("X1").TextString, adapter.entity("X1").Layer, adapter.entity("X1").Height) == (
        "DONE",
        "NOTES",
        4,
    )


def test_tff_uses_explicit_measured_content_width(monkeypatch: pytest.MonkeyPatch) -> None:
    adapter = FakeAdapter()
    install(monkeypatch, adapter)
    preview_request = live.LiveTffPreviewRequest(
        document_name="Drawing1.dwg",
        measurements=(live.LiveFrameMeasurement(handle="M1", measured_content_width=30),),
        mode=FrameFitMode.HEIGHT_MULTIPLE_PADDING,
        horizontal_padding_height_factor=1,
    )
    preview = live.preview_live_tff(preview_request)
    request = live.LiveTffExecuteRequest(
        **preview_request.model_dump(),
        expected_frames=preview["expected_frames"],
        approval_fingerprint=preview["approval_fingerprint"],
    )
    live.execute_live_tff(request)
    assert adapter.entity("M1").Width == pytest.approx(35)
