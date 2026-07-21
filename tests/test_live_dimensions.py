from __future__ import annotations

from types import SimpleNamespace

import pytest

import xicad_mcp.live_dimensions as live
from xicad_mcp.headless_core_batch1 import Point3D
from xicad_mcp.headless_core_batch2 import (
    DimensionOverrideDetachItem,
    DimensionTextSnapshot,
    LinearDimensionSnapshot,
    SourcePolicy,
)


def point(x: float, y: float) -> Point3D:
    return Point3D(x=x, y=y, z=0)


def dimension(handle: str, start: float, end: float) -> LinearDimensionSnapshot:
    return LinearDimensionSnapshot(
        handle=handle,
        extension_start=point(start, 0),
        extension_end=point(end, 0),
        dimension_line_point=point(0, 2),
        style_name="Standard",
        layer="DIM",
    )


class FakeEntity:
    def __init__(self, handle: str, *, override: str = "") -> None:
        self.Handle = handle
        self.TextOverride = override
        self.deleted = False

    def Delete(self) -> None:
        self.deleted = True


class FakeDoc:
    Name = "Drawing1.dwg"

    def __init__(self) -> None:
        self.undo_started = 0
        self.undo_ended = 0

    def StartUndoMark(self) -> None:
        self.undo_started += 1

    def EndUndoMark(self) -> None:
        self.undo_ended += 1


class FakeAdapter:
    def __init__(
        self,
        *,
        linear: tuple[LinearDimensionSnapshot, ...] = (),
        dtd: tuple[DimensionTextSnapshot, ...] = (),
    ) -> None:
        self.doc = FakeDoc()
        self.linear = {item.handle.casefold(): item for item in linear}
        self.dtd = {item.handle.casefold(): item for item in dtd}
        self.entities = {
            handle: FakeEntity(item.handle, override=item.current_override) for handle, item in self.dtd.items()
        }
        self.entities.update(
            {handle: FakeEntity(item.handle, override=item.text_override) for handle, item in self.linear.items()}
        )
        self.next_handle = 100

    def connect(self) -> FakeDoc:
        return self.doc

    def objects(self) -> dict[str, FakeEntity]:
        return {handle: entity for handle, entity in self.entities.items() if not entity.deleted}

    def entity(self, handle: str) -> FakeEntity:
        entity = self.objects().get(handle.casefold())
        if entity is None:
            raise ValueError(handle)
        return entity

    def read_dtd(self, handles: tuple[str, ...]) -> tuple[DimensionTextSnapshot, ...]:
        result = []
        for handle in handles:
            snapshot = self.dtd[handle.casefold()]
            result.append(snapshot.model_copy(update={"current_override": self.entity(handle).TextOverride}))
        return tuple(result)

    def read_linear(self, handle: str) -> LinearDimensionSnapshot:
        return self.linear[handle.casefold()]

    def _created(self) -> FakeEntity:
        self.next_handle += 1
        entity = FakeEntity(f"{self.next_handle:X}")
        self.entities[entity.Handle.casefold()] = entity
        return entity

    def create_text(self, spec: object) -> FakeEntity:
        entity = self._created()
        entity.TextString = spec.text
        entity.InsertionPoint = tuple(spec.insertion_point.model_dump().values())
        entity.Layer = spec.layer
        entity.StyleName = spec.text_style
        entity.Height = spec.text_height
        entity.Rotation = live.radians(spec.rotation_degrees)
        return entity

    def create_dimension(self, spec: object) -> FakeEntity:
        entity = self._created()
        self.linear[entity.Handle.casefold()] = LinearDimensionSnapshot(
            handle=entity.Handle,
            extension_start=spec.extension_start,
            extension_end=spec.extension_end,
            dimension_line_point=spec.dimension_line_point,
            style_name=spec.style_name,
            layer=spec.layer,
            text_override=spec.text_override,
        )
        return entity


def install(monkeypatch: pytest.MonkeyPatch, adapter: FakeAdapter) -> None:
    monkeypatch.setattr(live, "ZWCADLiveDimensionAdapter", lambda _name: adapter)


def test_dtd_preview_execute_and_postcondition(monkeypatch: pytest.MonkeyPatch) -> None:
    snapshot = DimensionTextSnapshot(
        handle="A1", current_override="1000 NOTE", layer="DIM", text_style="Standard", text_height=2.5
    )
    adapter = FakeAdapter(dtd=(snapshot,))
    install(monkeypatch, adapter)
    item = DimensionOverrideDetachItem(
        dimension_handle="A1",
        expected_current_override="1000 NOTE",
        replacement_override="1000",
        detached_text="NOTE",
        insertion_point=point(4, 2),
    )
    preview = live.preview_live_dtd(live.LiveDtdPreviewRequest(document_name="Drawing1.dwg", items=(item,)))
    request = live.LiveDtdExecuteRequest(
        document_name="Drawing1.dwg",
        items=(item,),
        expected_dimensions=tuple(DimensionTextSnapshot.model_validate(x) for x in preview["expected_dimensions"]),
        approval_fingerprint=preview["approval_fingerprint"],
    )
    result = live.execute_live_dtd(request)

    assert result.command_alias == "DTD"
    assert result.changed_handles == ("A1",)
    assert len(result.created_handles) == 1
    assert adapter.entity("A1").TextOverride == "1000"
    assert (adapter.doc.undo_started, adapter.doc.undo_ended) == (1, 1)


def test_dvd_replace_creates_segments_and_erases_source(monkeypatch: pytest.MonkeyPatch) -> None:
    source = dimension("B1", 0, 12)
    adapter = FakeAdapter(linear=(source,))
    install(monkeypatch, adapter)
    preview_request = live.LiveDividePreviewRequest(
        document_name="Drawing1.dwg", source_handle="B1", divisions=3, source_policy=SourcePolicy.REPLACE
    )
    preview = live.preview_live_dvd(preview_request)
    request = live.LiveDivideExecuteRequest(
        **preview_request.model_dump(),
        expected_source=LinearDimensionSnapshot.model_validate(preview["expected_source"]),
        approval_fingerprint=preview["approval_fingerprint"],
    )
    result = live.execute_live_dvd(request)

    assert len(result.created_handles) == 3
    assert result.erased_handles == ("B1",)
    assert "b1" not in adapter.objects()
    assert (adapter.doc.undo_started, adapter.doc.undo_ended) == (1, 1)


def test_jd_preserve_creates_one_dimension(monkeypatch: pytest.MonkeyPatch) -> None:
    sources = (dimension("C1", 0, 5), dimension("C2", 5, 10))
    adapter = FakeAdapter(linear=sources)
    install(monkeypatch, adapter)
    preview_request = live.LiveJoinPreviewRequest(
        document_name="Drawing1.dwg",
        source_handles=("C1", "C2"),
        source_policy=SourcePolicy.PRESERVE,
    )
    preview = live.preview_live_jd(preview_request)
    request = live.LiveJoinExecuteRequest(
        **preview_request.model_dump(),
        expected_sources=tuple(LinearDimensionSnapshot.model_validate(x) for x in preview["expected_sources"]),
        approval_fingerprint=preview["approval_fingerprint"],
    )
    result = live.execute_live_jd(request)

    assert len(result.created_handles) == 1
    assert result.erased_handles == ()
    assert {"c1", "c2"}.issubset(adapter.objects())


def test_fingerprint_rejects_changed_execution(monkeypatch: pytest.MonkeyPatch) -> None:
    source = dimension("B1", 0, 12)
    adapter = FakeAdapter(linear=(source,))
    install(monkeypatch, adapter)
    request = live.LiveDivideExecuteRequest(
        document_name="Drawing1.dwg",
        source_handle="B1",
        divisions=4,
        source_policy=SourcePolicy.PRESERVE,
        expected_source=source,
        approval_fingerprint="sha256:" + "0" * 64,
    )
    with pytest.raises(ValueError, match="fingerprint"):
        live.execute_live_dvd(request)
    assert adapter.doc.undo_started == 0


def test_adapter_truthfully_rejects_non_aligned_dimension() -> None:
    adapter = live.ZWCADLiveDimensionAdapter("Drawing1.dwg")
    adapter.doc = SimpleNamespace(ModelSpace=[SimpleNamespace(Handle="D1", ObjectName="AcDbRotatedDimension")])
    with pytest.raises(ValueError, match="aligned dimensions only"):
        adapter.read_linear("D1")


def test_adapter_reads_active_x_aligned_dimension_properties() -> None:
    adapter = live.ZWCADLiveDimensionAdapter("Drawing1.dwg")
    adapter.doc = SimpleNamespace(
        ModelSpace=[
            SimpleNamespace(
                Handle="D2",
                ObjectName="AcDbAlignedDimension",
                ExtLine1Point=(0, 0, 0),
                ExtLine2Point=(10, 0, 0),
                TextPosition=(5, 2, 0),
                StyleName="Standard",
                Layer="DIM",
                TextOverride="",
            )
        ]
    )
    snapshot = adapter.read_linear("D2")
    assert snapshot.dimension_line_point == point(5, 2)
