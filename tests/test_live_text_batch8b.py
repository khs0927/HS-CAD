from __future__ import annotations

from typing import Any

import pytest

from xicad_mcp.headless_core_batch1 import Point3D
from xicad_mcp.headless_core_batch8 import (
    ContainerAlignment,
    DynamicTitleRequest,
    EqualSpacingTextRequest,
    ShadowRepresentation,
    StyleMergeRequest,
    TextCenterRequest,
    TextContainerPair,
    TextShadowRequest,
)
from xicad_mcp.live_text_batch8b import (
    LiveDynamicTitleExecuteRequest,
    LiveEqualSpacingExecuteRequest,
    LiveStyleMergeExecuteRequest,
    LiveTextCenterCommand,
    LiveTextCenterExecuteRequest,
    LiveTextShadowExecuteRequest,
    execute_live_dat,
    execute_live_ltx,
    execute_live_to,
    execute_live_toa,
    execute_live_tsh,
    execute_live_tsm,
    preview_live_dat,
    preview_live_ltx,
    preview_live_to,
    preview_live_toa,
    preview_live_tsh,
    preview_live_tsm,
)


class FakeStyle:
    def __init__(self, name: str) -> None:
        self.Name = name


class FakeCollection:
    def __init__(self, names: tuple[str, ...], *, styles: bool = False) -> None:
        self.values = {
            name.casefold(): FakeStyle(name) if styles else type("Layer", (), {"Lock": False})()
            for name in names
        }

    def Item(self, name: str) -> Any:
        try:
            return self.values[name.casefold()]
        except KeyError as exc:
            raise RuntimeError(name) from exc

    def __iter__(self):
        return iter(self.values.values())


class FakeText:
    def __init__(self, block: FakeBlock, handle: str, text: str, x: float, style: str = "Standard") -> None:
        self.block = block
        self.Handle = handle
        self.ObjectName = "AcDbText"
        self.TextString = text
        self.Layer = "TEXT"
        self.StyleName = style
        self.Height = 2.5
        self.InsertionPoint = (x, 0.0, 0.0)
        self.Rotation = 0.0
        self.Color = 256

    def Copy(self) -> FakeText:
        return self.block.add(f"C{len(self.block.entities)}", self.TextString, self.InsertionPoint[0], self.StyleName)


class FakeContainer:
    def __init__(self, handle: str, low: tuple[float, float, float], high: tuple[float, float, float]) -> None:
        self.Handle = handle
        self.ObjectName = "AcDbPolyline"
        self.low = low
        self.high = high

    def GetBoundingBox(self):
        return self.low, self.high


class FakeBlock:
    def __init__(self) -> None:
        self.Name = "*Model_Space"
        self.IsLayout = True
        self.entities: list[Any] = []

    def add(self, handle: str, text: str, x: float, style: str = "Standard") -> FakeText:
        entity = FakeText(self, handle, text, x, style)
        self.entities.append(entity)
        return entity

    def AddText(self, text: str, point: tuple[float, float, float], height: float) -> FakeText:
        entity = self.add(f"N{len(self.entities)}", text, point[0])
        entity.InsertionPoint = point
        entity.Height = height
        return entity

    def __iter__(self):
        return iter(self.entities.copy())


class FakeDocument:
    def __init__(self) -> None:
        self.Name = "Drawing1.dwg"
        model = FakeBlock()
        model.add("A", "one", 1, "Old")
        model.add("B", "two", 2)
        model.entities.append(FakeContainer("R", (0, 0, 0), (20, 10, 0)))
        self.Blocks = [model]
        self.ModelSpace = model
        self.Layers = FakeCollection(("TEXT", "SHADOW", "TITLE"))
        self.TextStyles = FakeCollection(("Standard", "Old", "New"), styles=True)
        self.events: list[str] = []

    def StartUndoMark(self) -> None:
        self.events.append("start")

    def EndUndoMark(self) -> None:
        self.events.append("end")


@pytest.fixture
def doc(monkeypatch: pytest.MonkeyPatch) -> FakeDocument:
    value = FakeDocument()
    monkeypatch.setattr("xicad_mcp.live_text_batch8b._drawing", lambda _name: value)
    monkeypatch.setattr(
        "xicad_mcp.live_text_batch8b._variant_point",
        lambda point: (point.x, point.y, point.z),
    )
    return value


def center_execution(preview: dict[str, Any]) -> LiveTextCenterExecuteRequest:
    return LiveTextCenterExecuteRequest(
        command_alias=preview["command_alias"],
        request=preview["request"],
        expected_entities=preview["expected_entities"],
        expected_containers=preview["expected_containers"],
        approval_fingerprint=preview["approval_fingerprint"],
    )


@pytest.mark.parametrize("alias", [LiveTextCenterCommand.TO, LiveTextCenterCommand.TOA])
def test_to_and_toa_move_text_to_approved_container_center(
    doc: FakeDocument,
    alias: LiveTextCenterCommand,
) -> None:
    request = TextCenterRequest(
        document_id=doc.Name,
        pairs=(TextContainerPair(text_handle="A", container_handle="R"),),
        alignment=ContainerAlignment.CENTER,
    )
    preview = preview_live_to(request) if alias is LiveTextCenterCommand.TO else preview_live_toa(request)
    execution = center_execution(preview)
    result = execute_live_to(execution) if alias is LiveTextCenterCommand.TO else execute_live_toa(execution)
    assert doc.ModelSpace.entities[0].InsertionPoint == (10.0, 5.0, 0.0)
    assert result.changed_handles == ("A",)
    assert doc.events == ["start", "end"]


def test_container_drift_is_rejected_before_undo(doc: FakeDocument) -> None:
    request = TextCenterRequest(
        document_id=doc.Name,
        pairs=(TextContainerPair(text_handle="A", container_handle="R"),),
    )
    execution = center_execution(preview_live_to(request))
    doc.ModelSpace.entities[2].high = (30, 10, 0)
    with pytest.raises(ValueError, match="no longer matches"):
        execute_live_to(execution)
    assert doc.events == []


def test_tsh_text_copy_preserves_text_and_applies_shadow_properties(doc: FakeDocument) -> None:
    request = TextShadowRequest(
        document_id=doc.Name,
        target_handles=("A",),
        representation=ShadowRepresentation.TEXT_COPY,
        offset=Point3D(x=3, y=-2),
        layer="SHADOW",
        color_index=8,
    )
    preview = preview_live_tsh(request)
    execution = LiveTextShadowExecuteRequest(
        request=preview["request"],
        expected_entities=preview["expected_entities"],
        approval_fingerprint=preview["approval_fingerprint"],
    )
    result = execute_live_tsh(execution)
    copied = doc.ModelSpace.entities[-1]
    assert copied.TextString == "one"
    assert copied.InsertionPoint == (4.0, -2.0, 0.0)
    assert (copied.Layer, copied.Color) == ("SHADOW", 8)
    assert len(result.created_handles) == 1


def test_tsh_solid_outline_is_truthfully_blocked(doc: FakeDocument) -> None:
    request = TextShadowRequest(
        document_id=doc.Name,
        target_handles=("A",),
        representation=ShadowRepresentation.SOLID_OUTLINE,
        offset=Point3D(x=1, y=1),
        layer="SHADOW",
        color_index=8,
    )
    with pytest.raises(ValueError, match="solid outline"):
        preview_live_tsh(request)


def test_tsm_reassigns_document_text_without_unsafe_style_deletion(doc: FakeDocument) -> None:
    request = StyleMergeRequest(
        document_id=doc.Name,
        source_styles=("Old",),
        target_style="New",
        remove_source_styles=False,
    )
    preview = preview_live_tsm(request)
    execution = LiveStyleMergeExecuteRequest(
        request=preview["request"],
        expected_entities=preview["expected_entities"],
        expected_style_names=preview["expected_style_names"],
        approval_fingerprint=preview["approval_fingerprint"],
    )
    result = execute_live_tsm(execution)
    assert doc.ModelSpace.entities[0].StyleName == "New"
    assert result.changed_handles == ("A",)


def test_tsm_source_style_removal_is_blocked(doc: FakeDocument) -> None:
    request = StyleMergeRequest(
        document_id=doc.Name,
        source_styles=("Old",),
        target_style="New",
        remove_source_styles=True,
    )
    with pytest.raises(ValueError, match="non-text references"):
        preview_live_tsm(request)


def test_dat_creates_explicit_field_expression(doc: FakeDocument) -> None:
    request = DynamicTitleRequest(
        document_id=doc.Name,
        field_expression=r"%<\AcVar Filename>%",
        preview_text="Drawing1.dwg",
        insertion_point=Point3D(x=100, y=200),
        layer="TITLE",
        text_style="Standard",
        text_height=10,
    )
    preview = preview_live_dat(request)
    result = execute_live_dat(
        LiveDynamicTitleExecuteRequest(
            request=preview["request"], approval_fingerprint=preview["approval_fingerprint"]
        )
    )
    assert doc.ModelSpace.entities[-1].TextString == request.field_expression
    assert len(result.created_handles) == 1


def test_ltx_creates_equal_spaced_text_with_rotation(doc: FakeDocument) -> None:
    request = EqualSpacingTextRequest(
        document_id=doc.Name,
        texts=("A", "B", "C"),
        start_point=Point3D(x=10, y=20),
        step_vector=Point3D(x=5, y=-2),
        layer="TEXT",
        text_style="Standard",
        text_height=2.5,
        rotation_degrees=30,
    )
    preview = preview_live_ltx(request)
    result = execute_live_ltx(
        LiveEqualSpacingExecuteRequest(
            request=preview["request"], approval_fingerprint=preview["approval_fingerprint"]
        )
    )
    created = doc.ModelSpace.entities[-3:]
    assert [item.InsertionPoint for item in created] == [(10, 20, 0), (15, 18, 0), (20, 16, 0)]
    assert all(item.Rotation == pytest.approx(0.5235987756) for item in created)
    assert len(result.created_handles) == 3
