from __future__ import annotations

from typing import Any

import pytest

from xicad_mcp.headless_core_batch9 import (
    ChangeLayerRequest,
    ColorToLayerRequest,
    EntityPropertyPolicy,
    EntityVisibilityRequest,
    LayerMergeRequest,
    SetCurrentLayerRequest,
    TargetLayerMode,
    TargetLayerSpec,
)
from xicad_mcp.live_layer_batch9b import (
    LiveEwExecuteRequest,
    LiveLamExecuteRequest,
    LiveLccExecuteRequest,
    LiveLcExecuteRequest,
    LiveVisibilityCommand,
    LiveVisibilityExecuteRequest,
    execute_live_esf,
    execute_live_eso,
    execute_live_ew,
    execute_live_lam,
    execute_live_lc,
    execute_live_lcc,
    preview_live_esf,
    preview_live_eso,
    preview_live_ew,
    preview_live_lam,
    preview_live_lc,
    preview_live_lcc,
)


class FakeLayer:
    def __init__(self, name: str, *, locked: bool = False, frozen: bool = False, on: bool = True) -> None:
        self.Name = name
        self.Color = 7
        self.Linetype = "Continuous"
        self.LayerOn = on
        self.Freeze = frozen
        self.Lock = locked
        self.deleted = False

    def Delete(self) -> None:
        self.deleted = True


class FakeLayers:
    def __init__(self, *layers: FakeLayer) -> None:
        self.layers = list(layers)

    def Item(self, name: str) -> FakeLayer:
        return next(layer for layer in self.layers if not layer.deleted and layer.Name.casefold() == name.casefold())

    def Add(self, name: str) -> FakeLayer:
        layer = FakeLayer(name)
        self.layers.append(layer)
        return layer

    def __iter__(self):
        return iter(layer for layer in self.layers if not layer.deleted)


class FakeLinetypes:
    def Item(self, name: str) -> str:
        if name != "Continuous":
            raise RuntimeError(name)
        return name


class FakeEntity:
    def __init__(
        self,
        handle: str,
        layer: str,
        *,
        color: int = 256,
        visible: bool = True,
        block_name: str | None = None,
    ) -> None:
        self.Handle = handle
        self.Layer = layer
        self.Color = color
        self.Linetype = "ByLayer"
        self.Visible = visible
        self.ObjectName = "AcDbBlockReference" if block_name else "AcDbLine"
        self.EffectiveName = block_name


class FakeBlock:
    def __init__(self, *entities: FakeEntity) -> None:
        self.Name = "*Model_Space"
        self.Handle = "BLOCK"
        self.IsLayout = True
        self.IsXRef = False
        self.entities = list(entities)

    def __iter__(self):
        return iter(self.entities)


class FakeDocument:
    def __init__(self, *, locked_old: bool = False) -> None:
        zero = FakeLayer("0")
        old = FakeLayer("OLD", locked=locked_old)
        new = FakeLayer("NEW")
        self.Name = "Drawing1.dwg"
        self.Layers = FakeLayers(zero, old, new)
        self.ActiveLayer = zero
        self.Linetypes = FakeLinetypes()
        self.Blocks = [
            FakeBlock(
                FakeEntity("A", "OLD", color=3, block_name="CHAIR"),
                FakeEntity("B", "OLD", color=4, block_name="CHAIR"),
                FakeEntity("C", "NEW", color=3),
            )
        ]
        self.events: list[str] = []

    def StartUndoMark(self) -> None:
        self.events.append("start")

    def EndUndoMark(self) -> None:
        self.events.append("end")


@pytest.fixture
def doc(monkeypatch: pytest.MonkeyPatch) -> FakeDocument:
    value = FakeDocument()
    monkeypatch.setattr("xicad_mcp.live_layer_batch9b._drawing", lambda _name: value)
    return value


def visibility_execution(preview: dict[str, Any]) -> LiveVisibilityExecuteRequest:
    return LiveVisibilityExecuteRequest(
        command_alias=preview["command_alias"],
        request=preview["request"],
        expected_layers=preview["expected_layers"],
        expected_entities=preview["expected_entities"],
        approval_fingerprint=preview["approval_fingerprint"],
    )


@pytest.mark.parametrize("alias", [LiveVisibilityCommand.ESF, LiveVisibilityCommand.ESO])
def test_esf_and_eso_apply_exact_visibility_plan(doc: FakeDocument, alias: LiveVisibilityCommand) -> None:
    request = EntityVisibilityRequest(document_id=doc.Name, selected_handles=("A",))
    preview = preview_live_esf(request) if alias is LiveVisibilityCommand.ESF else preview_live_eso(request)
    execution = visibility_execution(preview)
    result = execute_live_esf(execution) if alias is LiveVisibilityCommand.ESF else execute_live_eso(execution)
    assert doc.Blocks[0].entities[0].Visible is (alias is LiveVisibilityCommand.ESO)
    assert result.postcondition_verified
    assert doc.events == ["start", "end"]


def test_visibility_on_locked_layer_is_rejected_before_undo(monkeypatch: pytest.MonkeyPatch) -> None:
    doc = FakeDocument(locked_old=True)
    monkeypatch.setattr("xicad_mcp.live_layer_batch9b._drawing", lambda _name: doc)
    execution = visibility_execution(
        preview_live_esf(EntityVisibilityRequest(document_id=doc.Name, selected_handles=("A",)))
    )
    with pytest.raises(ValueError, match="locked layer"):
        execute_live_esf(execution)
    assert doc.events == []


def test_ew_sets_source_entity_layer_current(doc: FakeDocument) -> None:
    request = SetCurrentLayerRequest(document_id=doc.Name, source_entity_handle="A")
    preview = preview_live_ew(request)
    result = execute_live_ew(
        LiveEwExecuteRequest(
            request=preview["request"], expected_layers=preview["expected_layers"],
            expected_entities=preview["expected_entities"], approval_fingerprint=preview["approval_fingerprint"],
        )
    )
    assert doc.ActiveLayer.Name == "OLD"
    assert result.current_layer == "OLD"


def test_lam_moves_entities_and_removes_empty_source(doc: FakeDocument) -> None:
    request = LayerMergeRequest(
        document_id=doc.Name,
        source_layers=("OLD",),
        target_layer="NEW",
        include_nested=False,
        preserve_entity_color=True,
        preserve_entity_linetype=False,
        remove_source_layers=True,
    )
    preview = preview_live_lam(request)
    result = execute_live_lam(
        LiveLamExecuteRequest(
            request=preview["request"], expected_layers=preview["expected_layers"],
            expected_entities=preview["expected_entities"], approval_fingerprint=preview["approval_fingerprint"],
        )
    )
    assert [entity.Layer for entity in doc.Blocks[0].entities[:2]] == ["NEW", "NEW"]
    assert result.removed_layers == ("OLD",)


def test_lc_changes_selected_entity_and_resets_properties(doc: FakeDocument) -> None:
    request = ChangeLayerRequest(
        document_id=doc.Name,
        target_handles=("A",),
        target_layer=TargetLayerSpec(mode=TargetLayerMode.EXISTING, name="NEW"),
        color_policy=EntityPropertyPolicy.BY_LAYER,
        linetype_policy=EntityPropertyPolicy.BY_LAYER,
    )
    preview = preview_live_lc(request)
    result = execute_live_lc(
        LiveLcExecuteRequest(
            request=preview["request"], expected_layers=preview["expected_layers"],
            expected_entities=preview["expected_entities"], approval_fingerprint=preview["approval_fingerprint"],
        )
    )
    entity = doc.Blocks[0].entities[0]
    assert (entity.Layer, entity.Color, entity.Linetype) == ("NEW", 256, "ByLayer")
    assert result.changed_handles == ("A",)


def test_lc_can_create_complete_target_layer(doc: FakeDocument) -> None:
    request = ChangeLayerRequest(
        document_id=doc.Name,
        target_handles=("A",),
        target_layer=TargetLayerSpec(
            mode=TargetLayerMode.CREATE, name="CREATED", color_index=2, linetype="Continuous"
        ),
        color_policy=EntityPropertyPolicy.PRESERVE,
        linetype_policy=EntityPropertyPolicy.PRESERVE,
    )
    preview = preview_live_lc(request)
    execution = LiveLcExecuteRequest(
        request=preview["request"], expected_layers=preview["expected_layers"],
        expected_entities=preview["expected_entities"], approval_fingerprint=preview["approval_fingerprint"],
    )
    result = execute_live_lc(execution)
    assert doc.Layers.Item("CREATED").Color == 2
    assert result.changed_layers == ("CREATED",)


def test_lcc_moves_only_matching_color_entities(doc: FakeDocument) -> None:
    request = ColorToLayerRequest(
        document_id=doc.Name,
        source_color_indices=(3,),
        target_layer=TargetLayerSpec(mode=TargetLayerMode.EXISTING, name="NEW"),
    )
    preview = preview_live_lcc(request)
    result = execute_live_lcc(
        LiveLccExecuteRequest(
            request=preview["request"], expected_layers=preview["expected_layers"],
            expected_entities=preview["expected_entities"], approval_fingerprint=preview["approval_fingerprint"],
        )
    )
    assert result.changed_handles == ("A", "C")
    assert doc.Blocks[0].entities[1].Layer == "OLD"


def test_inventory_drift_is_rejected_before_undo(doc: FakeDocument) -> None:
    request = SetCurrentLayerRequest(document_id=doc.Name, source_entity_handle="A")
    preview = preview_live_ew(request)
    execution = LiveEwExecuteRequest(
        request=preview["request"], expected_layers=preview["expected_layers"],
        expected_entities=preview["expected_entities"], approval_fingerprint=preview["approval_fingerprint"],
    )
    doc.Blocks[0].entities[0].Color = 9
    with pytest.raises(ValueError, match="inventory"):
        execute_live_ew(execution)
    assert doc.events == []
