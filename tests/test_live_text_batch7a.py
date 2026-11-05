from __future__ import annotations

from types import SimpleNamespace

import pytest

import xicad_mcp.live_text_batch7a as live
from xicad_mcp.headless_core_batch1 import Point3D
from xicad_mcp.headless_core_batch5 import DrawingSpace, TextEntityKind, TextEntitySnapshot
from xicad_mcp.headless_core_batch7 import (
    MarkShape,
    SearchMode,
    SourceDisposition,
    TextJustification,
    UnresolvedFieldPolicy,
)


def snapshot(handle: str, text: str, *, kind: TextEntityKind = TextEntityKind.TEXT) -> TextEntitySnapshot:
    return TextEntitySnapshot(
        handle=handle,
        text=text,
        kind=kind,
        layer="TEXT",
        text_style="Standard",
        text_height=2.5,
        insertion_point=Point3D(x=float(int(handle[-1], 16)), y=2, z=0),
        space=DrawingSpace.MODEL,
    )


class FakeEntity:
    def __init__(self, item: TextEntitySnapshot) -> None:
        self.Handle = item.handle
        self.TextString = item.text
        self.Layer = item.layer
        self.StyleName = item.text_style
        self.Height = item.text_height
        self.TextHeight = item.text_height
        self.Rotation = 0.0
        self.Alignment = 0
        self.AttachmentPoint = 1
        self.deleted = False

    def Delete(self) -> None:
        self.deleted = True

    def Move(self, _source: object, _target: object) -> None:
        pass


class FakeSpace:
    def __init__(self, adapter: FakeAdapter) -> None:
        self.adapter = adapter

    def AddCircle(self, _center: object, radius: float) -> FakeEntity:
        entity = self.adapter.created("SEARCH")
        entity.Radius = radius
        return entity

    def InsertBlock(self, _point: object, name: str, *_args: object) -> FakeEntity:
        entity = self.adapter.created(name)
        entity.Name = name
        return entity

    def AddPoint(self, _point: object) -> FakeEntity:
        return self.adapter.created("POINT")

    def AddMText(self, _point: object, _width: float, text: str) -> FakeEntity:
        return self.adapter.created(text, kind=TextEntityKind.MTEXT)


class FakeDoc:
    Name = "Drawing1.dwg"

    def __init__(self, adapter: FakeAdapter) -> None:
        self.ModelSpace = FakeSpace(adapter)
        self.TextStyles = SimpleNamespace(Item=lambda _name: object())
        self.started = 0
        self.ended = 0

    def StartUndoMark(self) -> None:
        self.started += 1

    def EndUndoMark(self) -> None:
        self.ended += 1


class FakeAdapter:
    def __init__(self, items: tuple[TextEntitySnapshot, ...]) -> None:
        self.items = {item.handle.casefold(): item for item in items}
        self.entities = {handle: FakeEntity(item) for handle, item in self.items.items()}
        self.doc = FakeDoc(self)
        self.counter = 0x100

    def connect(self) -> FakeDoc:
        return self.doc

    def snapshots(self, handles: tuple[str, ...] | None = None) -> tuple[TextEntitySnapshot, ...]:
        values = tuple(self.items.values())
        if handles is not None:
            wanted = {handle.casefold() for handle in handles}
            values = tuple(item for item in values if item.handle.casefold() in wanted)
        return tuple(sorted(values, key=lambda item: item.handle.casefold()))

    def fields(self, resolutions: tuple[live.LiveFieldResolution, ...]) -> tuple[object, ...]:
        from xicad_mcp.headless_core_batch7 import FieldTextSnapshot

        return tuple(
            FieldTextSnapshot(
                handle=item.handle,
                field_expression=item.field_expression,
                evaluated_text=item.evaluated_text,
                literal_fallback=item.literal_fallback,
            )
            for item in resolutions
        )

    def entity(self, handle: str) -> FakeEntity:
        return self.entities[handle.casefold()]

    def owner(self, _handle: str) -> FakeSpace:
        return self.doc.ModelSpace

    def objects(self) -> dict[str, FakeEntity]:
        return {handle: entity for handle, entity in self.entities.items() if not entity.deleted}

    def vector(self, point: Point3D) -> tuple[float, float, float]:
        return (point.x, point.y, point.z)

    def bbox(self, _entity: FakeEntity) -> tuple[Point3D, Point3D]:
        return Point3D(x=0, y=0, z=0), Point3D(x=10, y=3, z=0)

    def created(self, text: str, *, kind: TextEntityKind = TextEntityKind.TEXT) -> FakeEntity:
        self.counter += 1
        item = snapshot(f"{self.counter:X}", text, kind=kind)
        entity = FakeEntity(item)
        self.entities[item.handle.casefold()] = entity
        return entity


def install(monkeypatch: pytest.MonkeyPatch, adapter: FakeAdapter) -> None:
    monkeypatch.setattr(live, "ZWCADLiveText7aAdapter", lambda _name: adapter)


def test_fam_circle_marks_matching_text(monkeypatch: pytest.MonkeyPatch) -> None:
    adapter = FakeAdapter((snapshot("A1", "ROOM 101"), snapshot("A2", "ROOM 202")))
    install(monkeypatch, adapter)
    preview_request = live.LiveFamPreviewRequest(
        document_name="Drawing1.dwg",
        query="101",
        mode=SearchMode.MARK,
        mark_shape=MarkShape.CIRCLE,
        mark_layer="MARK",
        circle_radius=3,
    )
    preview = live.preview_live_fam(preview_request)
    request = live.LiveFamExecuteRequest(
        **preview_request.model_dump(),
        expected_entities=tuple(TextEntitySnapshot.model_validate(x) for x in preview["expected_entities"]),
        approval_fingerprint=preview["approval_fingerprint"],
    )
    result = live.execute_live_fam(request)
    assert result.matched_handles == ("A1",)
    assert len(result.created_handles) == 1
    assert adapter.doc.started == adapter.doc.ended == 1


def test_ftt_uses_explicit_evaluated_value(monkeypatch: pytest.MonkeyPatch) -> None:
    expression = "%<\\AcVar Date>%"
    adapter = FakeAdapter((snapshot("A1", expression),))
    install(monkeypatch, adapter)
    preview_request = live.LiveFttPreviewRequest(
        document_name="Drawing1.dwg",
        resolutions=(live.LiveFieldResolution(handle="A1", field_expression=expression, evaluated_text="2026-07-21"),),
        unresolved_policy=UnresolvedFieldPolicy.ERROR,
    )
    preview = live.preview_live_ftt(preview_request)
    request = live.LiveFttExecuteRequest(
        **preview_request.model_dump(),
        expected_fields=preview["expected_fields"],
        approval_fingerprint=preview["approval_fingerprint"],
    )
    result = live.execute_live_ftt(request)
    assert result.changed_handles == ("A1",)
    assert adapter.entity("A1").TextString == "2026-07-21"


def test_t2m_replaces_text_with_mtext(monkeypatch: pytest.MonkeyPatch) -> None:
    adapter = FakeAdapter((snapshot("A1", "TITLE"),))
    install(monkeypatch, adapter)
    preview_request = live.LiveT2mPreviewRequest(
        document_name="Drawing1.dwg",
        target_handles=("A1",),
        source_disposition=SourceDisposition.REPLACE,
        preserve_visual_width=True,
    )
    preview = live.preview_live_t2m(preview_request)
    request = live.LiveT2mExecuteRequest(
        **preview_request.model_dump(),
        expected_entities=preview["expected_entities"],
        approval_fingerprint=preview["approval_fingerprint"],
    )
    result = live.execute_live_t2m(request)
    assert len(result.created_handles) == 1
    assert result.erased_handles == ("A1",)


def test_tec_returns_extraction_without_undo(monkeypatch: pytest.MonkeyPatch) -> None:
    adapter = FakeAdapter((snapshot("A1", "ROOM-012"),))
    install(monkeypatch, adapter)
    preview_request = live.LiveTecPreviewRequest(
        document_name="Drawing1.dwg", target_handles=("A1",), mode="slice", start=5, end=8
    )
    preview = live.preview_live_tec(preview_request)
    request = live.LiveTecExecuteRequest(
        **preview_request.model_dump(),
        expected_entities=preview["expected_entities"],
        approval_fingerprint=preview["approval_fingerprint"],
    )
    result = live.execute_live_tec(request)
    assert result.extracted_values == ("012",)
    assert adapter.doc.started == 0


def test_tj_changes_text_alignment(monkeypatch: pytest.MonkeyPatch) -> None:
    adapter = FakeAdapter((snapshot("A1", "CENTER ME"),))
    install(monkeypatch, adapter)
    preview_request = live.LiveTjPreviewRequest(
        document_name="Drawing1.dwg",
        target_handles=("A1",),
        justification=TextJustification.CENTER,
        preserve_visual_position=True,
    )
    preview = live.preview_live_tj(preview_request)
    request = live.LiveTjExecuteRequest(
        **preview_request.model_dump(),
        expected_entities=preview["expected_entities"],
        approval_fingerprint=preview["approval_fingerprint"],
    )
    result = live.execute_live_tj(request)
    assert result.changed_handles == ("A1",)
    assert adapter.entity("A1").Alignment == 1


def test_tsa_changes_document_text_styles(monkeypatch: pytest.MonkeyPatch) -> None:
    adapter = FakeAdapter((snapshot("A1", "ONE"), snapshot("A2", "TWO")))
    install(monkeypatch, adapter)
    preview_request = live.LiveTsaPreviewRequest(document_name="Drawing1.dwg", target_style="ROMANS")
    preview = live.preview_live_tsa(preview_request)
    request = live.LiveTsaExecuteRequest(
        **preview_request.model_dump(),
        expected_entities=preview["expected_entities"],
        approval_fingerprint=preview["approval_fingerprint"],
    )
    result = live.execute_live_tsa(request)
    assert result.changed_handles == ("A1", "A2")
    assert all(entity.StyleName == "ROMANS" for entity in adapter.entities.values())


def test_fam_rejects_geometry_missing_from_contract(monkeypatch: pytest.MonkeyPatch) -> None:
    install(monkeypatch, FakeAdapter((snapshot("A1", "X"),)))
    request = live.LiveFamPreviewRequest(
        document_name="Drawing1.dwg", query="X", mode=SearchMode.MARK, mark_shape=MarkShape.BOX, mark_layer="MARK"
    )
    with pytest.raises(ValueError, match="absent"):
        live.preview_live_fam(request)
