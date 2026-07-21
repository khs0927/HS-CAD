from __future__ import annotations

from math import radians

import pytest

import xicad_mcp.live_annotations as live
from xicad_mcp.headless_core_batch1 import Point3D
from xicad_mcp.headless_core_batch3 import (
    AttributeBlockSnapshot,
    AttributePreservation,
    BlockRecordSnapshot,
    GhostClassification,
    RotationMode,
)


class FakeDoc:
    Name = "Drawing1.dwg"

    def __init__(self) -> None:
        self.started = 0
        self.ended = 0

    def StartUndoMark(self) -> None:
        self.started += 1

    def EndUndoMark(self) -> None:
        self.ended += 1


class FakeAttribute:
    def __init__(self, handle: str, x: float, rotation: float) -> None:
        self.Handle = handle
        self.InsertionPoint = (x, 2.0, 0.0)
        self.Rotation = rotation


class FakeBlockReference:
    def __init__(self) -> None:
        self.Handle = "B1"
        self.Name = "TAG_BLOCK"
        self.Rotation = radians(10)
        self.InsertionPoint = (0.0, 0.0, 0.0)
        self.attributes = [FakeAttribute("A1", 2.0, radians(5))]

    def GetAttributes(self) -> list[FakeAttribute]:
        return self.attributes

    def Rotate(self, _base: object, delta: float) -> None:
        self.Rotation += delta
        for attribute in self.attributes:
            attribute.Rotation += delta
            attribute.InsertionPoint = (attribute.InsertionPoint[0] + 1, 2.0, 0.0)


class FakeRecord:
    def __init__(self, snapshot: BlockRecordSnapshot) -> None:
        self.snapshot = snapshot
        self.deleted = False

    def Delete(self) -> None:
        self.deleted = True


class FakeAdapter:
    def __init__(self) -> None:
        self.doc = FakeDoc()
        self.reference = FakeBlockReference()
        snapshots = (
            BlockRecordSnapshot(handle="10", name="EMPTY", reference_count=0, entity_count=0),
            BlockRecordSnapshot(handle="11", name="USED", reference_count=1, entity_count=2),
            BlockRecordSnapshot(
                handle="12",
                name="*Model_Space",
                reference_count=0,
                entity_count=1,
                is_layout=True,
                is_system=True,
            ),
        )
        self.records = {snapshot.handle.casefold(): FakeRecord(snapshot) for snapshot in snapshots}

    def connect(self) -> FakeDoc:
        return self.doc

    def vector(self, point: Point3D) -> tuple[float, float, float]:
        return (point.x, point.y, point.z)

    def block_reference(self, handle: str) -> FakeBlockReference:
        if handle.casefold() != "b1":
            raise ValueError(handle)
        return self.reference

    def read_bar(self, handles: tuple[str, ...]) -> tuple[live.LiveAttributeBlockSnapshot, ...]:
        assert handles == ("B1",)
        attributes = tuple(
            live.LiveAttributeState(
                handle=attribute.Handle,
                insertion_point=Point3D(
                    x=attribute.InsertionPoint[0],
                    y=attribute.InsertionPoint[1],
                    z=attribute.InsertionPoint[2],
                ),
                rotation_radians=attribute.Rotation,
            )
            for attribute in self.reference.attributes
        )
        return (
            live.LiveAttributeBlockSnapshot(
                block=AttributeBlockSnapshot(
                    handle="B1",
                    block_name="TAG_BLOCK",
                    current_rotation_degrees=self.reference.Rotation * 180 / 3.141592653589793,
                    attribute_handles=tuple(item.handle for item in attributes),
                    non_attribute_entity_count=2,
                ),
                attributes=attributes,
            ),
        )

    def list_block_records(self) -> tuple[BlockRecordSnapshot, ...]:
        return tuple(record.snapshot for record in self.records.values() if not record.deleted)

    def block_records(self) -> dict[str, FakeRecord]:
        return {handle: record for handle, record in self.records.items() if not record.deleted}


def install(monkeypatch: pytest.MonkeyPatch, adapter: FakeAdapter) -> None:
    monkeypatch.setattr(live, "ZWCADLiveAnnotationAdapter", lambda _name: adapter)


def test_bar_preserves_attribute_world_transform(monkeypatch: pytest.MonkeyPatch) -> None:
    adapter = FakeAdapter()
    install(monkeypatch, adapter)
    preview_request = live.LiveBarPreviewRequest(
        document_name="Drawing1.dwg",
        block_handles=("B1",),
        rotation_mode=RotationMode.DELTA,
        angle_degrees=30,
        attribute_preservation=AttributePreservation.WORLD_POSITION_AND_ROTATION,
    )
    preview = live.preview_live_bar(preview_request)
    execute_request = live.LiveBarExecuteRequest(
        **preview_request.model_dump(),
        expected_blocks=tuple(
            live.LiveAttributeBlockSnapshot.model_validate(item) for item in preview["expected_blocks"]
        ),
        approval_fingerprint=preview["approval_fingerprint"],
    )
    result = live.execute_live_bar(execute_request)

    assert result.changed_handles == ("B1",)
    assert adapter.reference.Rotation == pytest.approx(radians(40))
    assert adapter.reference.attributes[0].Rotation == pytest.approx(radians(5))
    assert adapter.reference.attributes[0].InsertionPoint == (2.0, 2.0, 0.0)
    assert (adapter.doc.started, adapter.doc.ended) == (1, 1)


def test_abd_deletes_only_approved_empty_record(monkeypatch: pytest.MonkeyPatch) -> None:
    adapter = FakeAdapter()
    install(monkeypatch, adapter)
    preview_request = live.LiveAbdPreviewRequest(document_name="Drawing1.dwg")
    preview = live.preview_live_abd(preview_request)
    assert preview["plan"]["purge_names"] == ["EMPTY"]
    execute_request = live.LiveAbdExecuteRequest(
        **preview_request.model_dump(),
        expected_records=tuple(BlockRecordSnapshot.model_validate(item) for item in preview["expected_records"]),
        approval_fingerprint=preview["approval_fingerprint"],
    )
    result = live.execute_live_abd(execute_request)

    assert result.removed_handles == ("10",)
    assert adapter.records["10"].deleted is True
    assert adapter.records["11"].deleted is False
    assert (adapter.doc.started, adapter.doc.ended) == (1, 1)


def test_bar_rejects_stale_fingerprint_before_undo(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    adapter = FakeAdapter()
    install(monkeypatch, adapter)
    request = live.LiveBarExecuteRequest(
        document_name="Drawing1.dwg",
        block_handles=("B1",),
        rotation_mode=RotationMode.DELTA,
        angle_degrees=30,
        attribute_preservation=AttributePreservation.FOLLOW_BLOCK,
        expected_blocks=adapter.read_bar(("B1",)),
        approval_fingerprint="sha256:" + "0" * 64,
    )
    with pytest.raises(ValueError, match="fingerprint"):
        live.execute_live_bar(request)
    assert adapter.doc.started == 0


def test_agd_truthfully_reports_missing_active_x_capability() -> None:
    request = live.LiveAgdPreviewRequest(
        document_name="Drawing1.dwg",
        accepted_classifications=(GhostClassification.ORPHANED_OWNER,),
    )
    with pytest.raises(RuntimeError, match="not enumerable|not.*enumerable"):
        live.preview_live_agd(request)
