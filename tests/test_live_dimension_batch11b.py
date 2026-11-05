from __future__ import annotations

from typing import Any

import pytest

from xicad_mcp.headless_core_batch1 import Point3D
from xicad_mcp.headless_core_batch11 import (
    BaselineSide,
    ContinueDimensionRequest,
    ContinueGapSource,
    DimensionExtensionToggleRequest,
    DimensionGapRequest,
    DimensionScaleBasis,
    DimensionTextHomeRequest,
    ExtensionArrangeRequest,
    ExtensionLengthRequest,
    ExtensionLineTarget,
    SuppressionOperation,
)
from xicad_mcp.live_dimension_batch11b import (
    LiveDdtExecuteRequest,
    LiveDeExecuteRequest,
    LiveDlaExecuteRequest,
    LiveDllExecuteRequest,
    execute_live_ddt,
    execute_live_de,
    execute_live_dla,
    execute_live_dll,
    preview_live_ddt,
    preview_live_de,
    preview_live_dg,
    preview_live_dh,
    preview_live_dla,
    preview_live_dll,
)


class FakeLayer:
    Lock = False


class FakeLayers:
    def Item(self, _name: str) -> FakeLayer:
        return FakeLayer()


class FakeDimension:
    def __init__(self, block: FakeBlock, handle: str, x1: float, x2: float) -> None:
        self.block = block
        self.Handle = handle
        self.ObjectName = "AcDbAlignedDimension"
        self.Layer = "DIM"
        self.StyleName = "ISO-25"
        self.Measurement = x2 - x1
        self.TextOverride = ""
        self.TextPosition = ((x1 + x2) / 2, 10.0, 0.0)
        self.ExtLine1Point = (x1, 0.0, 0.0)
        self.ExtLine2Point = (x2, 0.0, 0.0)
        self.ExtLine1Suppress = False
        self.ExtLine2Suppress = False
        self.ExtensionLineExtend = 1.25
        self.ScaleFactor = 2.0
        self.LinetypeScale = 1.0

    def Copy(self) -> FakeDimension:
        copied = FakeDimension(
            self.block,
            f"N{len(self.block.entities)}",
            self.ExtLine1Point[0],
            self.ExtLine2Point[0],
        )
        copied.TextPosition = self.TextPosition
        copied.StyleName = self.StyleName
        copied.TextOverride = self.TextOverride
        self.block.entities.append(copied)
        return copied


class FakeBlock:
    def __init__(self) -> None:
        self.Name = "*Model_Space"
        self.IsLayout = True
        self.entities: list[FakeDimension] = []

    def __iter__(self):
        return iter(self.entities.copy())


class FakeDocument:
    def __init__(self) -> None:
        self.Name = "Drawing1.dwg"
        block = FakeBlock()
        block.entities.extend(
            [FakeDimension(block, "A", 0, 10), FakeDimension(block, "B", 10, 20)]
        )
        self.Blocks = [block]
        self.Layers = FakeLayers()
        self.events: list[str] = []

    def StartUndoMark(self) -> None:
        self.events.append("start")

    def EndUndoMark(self) -> None:
        self.events.append("end")


@pytest.fixture
def doc(monkeypatch: pytest.MonkeyPatch) -> FakeDocument:
    value = FakeDocument()
    monkeypatch.setattr("xicad_mcp.live_dimension_batch11b._drawing", lambda _name: value)
    monkeypatch.setattr(
        "xicad_mcp.live_dimension_batch11b._variant",
        lambda point: (point.x, point.y, point.z),
    )
    return value


def execution(model: type[Any], preview: dict[str, Any]) -> Any:
    return model(
        request=preview["request"],
        expected_dimensions=preview["expected_dimensions"],
        approval_fingerprint=preview["approval_fingerprint"],
    )


def test_ddt_toggles_extension_suppression(doc: FakeDocument) -> None:
    request = DimensionExtensionToggleRequest(
        document_id=doc.Name,
        target_handles=("A",),
        target=ExtensionLineTarget.FIRST,
        operation=SuppressionOperation.TOGGLE,
    )
    result = execute_live_ddt(execution(LiveDdtExecuteRequest, preview_live_ddt(request)))
    assert doc.Blocks[0].entities[0].ExtLine1Suppress is True
    assert doc.Blocks[0].entities[0].ExtLine2Suppress is False
    assert result.changed_handles == ("A",)
    assert doc.events == ["start", "end"]


def test_de_copies_aligned_dimension_for_each_continuation(doc: FakeDocument) -> None:
    request = ContinueDimensionRequest(
        document_id=doc.Name,
        source_handle="A",
        continuation_points=(Point3D(x=20, y=0), Point3D(x=30, y=0)),
        gap_source=ContinueGapSource.SCREEN_DISTANCE,
        screen_distance=5,
    )
    result = execute_live_de(execution(LiveDeExecuteRequest, preview_live_de(request)))
    created = doc.Blocks[0].entities[-2:]
    assert [item.ExtLine1Point for item in created] == [(10, 0, 0), (20, 0, 0)]
    assert [item.ExtLine2Point for item in created] == [(20, 0, 0), (30, 0, 0)]
    assert len(result.created_handles) == 2


def test_dla_changes_only_requested_extension_origin(doc: FakeDocument) -> None:
    request = ExtensionArrangeRequest(
        document_id=doc.Name,
        target_handles=("A",),
        target=ExtensionLineTarget.SECOND,
        second_alignment_point=Point3D(x=15, y=2),
    )
    result = execute_live_dla(execution(LiveDlaExecuteRequest, preview_live_dla(request)))
    dimension = doc.Blocks[0].entities[0]
    assert dimension.ExtLine1Point == (0, 0, 0)
    assert dimension.ExtLine2Point == (15, 2, 0)
    assert result.postcondition_verified


def test_dll_both_uses_proven_shared_extension_length(doc: FakeDocument) -> None:
    request = ExtensionLengthRequest(
        document_id=doc.Name,
        target_handles=("A",),
        target=ExtensionLineTarget.BOTH,
        length_factor=3,
        scale_basis=DimensionScaleBasis.OBJECT_SCALE,
    )
    result = execute_live_dll(execution(LiveDllExecuteRequest, preview_live_dll(request)))
    assert doc.Blocks[0].entities[0].ExtensionLineExtend == 6
    assert result.changed_handles == ("A",)


def test_dll_individual_side_is_truthfully_blocked(doc: FakeDocument) -> None:
    request = ExtensionLengthRequest(
        document_id=doc.Name,
        target_handles=("A",),
        target=ExtensionLineTarget.FIRST,
        length_factor=3,
        scale_basis=DimensionScaleBasis.OBJECT_SCALE,
    )
    with pytest.raises(ValueError, match="shared"):
        preview_live_dll(request)


def test_dg_is_blocked_without_editable_dimension_line_point(doc: FakeDocument) -> None:
    request = DimensionGapRequest(
        document_id=doc.Name,
        ordered_handles=("A", "B"),
        gap_factor=1,
        scale_basis=DimensionScaleBasis.OBJECT_SCALE,
        baseline_side=BaselineSide.INSIDE,
        unit_offset_direction=Point3D(x=0, y=1),
    )
    with pytest.raises(ValueError, match="dimension-line point"):
        preview_live_dg(request)


def test_dh_is_blocked_without_default_text_position(doc: FakeDocument) -> None:
    request = DimensionTextHomeRequest(document_id=doc.Name, target_handles=("A",))
    with pytest.raises(ValueError, match="default text-position"):
        preview_live_dh(request)


def test_dimension_drift_is_rejected_before_undo(doc: FakeDocument) -> None:
    request = DimensionExtensionToggleRequest(
        document_id=doc.Name,
        target_handles=("A",),
        target=ExtensionLineTarget.BOTH,
        operation=SuppressionOperation.HIDE,
    )
    preview = preview_live_ddt(request)
    approved = execution(LiveDdtExecuteRequest, preview)
    doc.Blocks[0].entities[0].TextOverride = "changed"
    with pytest.raises(ValueError, match="no longer matches"):
        execute_live_ddt(approved)
    assert doc.events == []
