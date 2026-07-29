from __future__ import annotations

import pytest

import xicad_mcp.live_layer_batch9a as live
from xicad_mcp.headless_core_batch1 import DrawingSpace
from xicad_mcp.headless_core_batch9 import DrawOrderDirection, LayerEntitySnapshot, LayerSnapshot


class FakeLayer:
    def __init__(self, name: str, *, on: bool = True, frozen: bool = False, current: bool = False) -> None:
        self.Name, self.LayerOn, self.Freeze = name, on, frozen
        self.Color, self.Linetype, self.Lock = 7, "Continuous", False
        self.current, self.deleted = current, False

    def Delete(self) -> None:
        self.deleted = True


class FakeEntity:
    def __init__(self, handle: str, layer: str, *, visible: bool = True) -> None:
        self.Handle, self.Layer, self.Visible = handle, layer, visible
        self.Color, self.Linetype, self.deleted = 256, "ByLayer", False

    def Delete(self) -> None:
        self.deleted = True


class FakeDoc:
    Name = "Drawing1.dwg"

    def __init__(self) -> None:
        self.started = self.ended = 0

    def StartUndoMark(self) -> None:
        self.started += 1

    def EndUndoMark(self) -> None:
        self.ended += 1


class FakeSortents:
    def __init__(self, entities: list[FakeEntity]) -> None:
        self.order = entities

    def MoveToTop(self, entities: list[FakeEntity]) -> None:
        for entity in entities:
            self.order.remove(entity)
            self.order.append(entity)

    def GetFullDrawOrder(self, _honor: bool) -> list[FakeEntity]:
        return self.order


class FakeAdapter:
    def __init__(self) -> None:
        self.doc = FakeDoc()
        self.layer_records = {
            "0": FakeLayer("0", current=True),
            "defpoints": FakeLayer("Defpoints"),
            "a": FakeLayer("A"),
            "b": FakeLayer("B", on=False),
            "erase": FakeLayer("ERASE"),
        }
        self.entities = {
            "e1": FakeEntity("E1", "A"),
            "e2": FakeEntity("E2", "B", visible=False),
            "e3": FakeEntity("E3", "ERASE"),
        }
        self.owner = object()
        self.sort_table = FakeSortents(list(self.entities.values()))

    def connect(self) -> FakeDoc:
        return self.doc

    def layers(self) -> tuple[LayerSnapshot, ...]:
        return tuple(
            sorted(
                (
                    LayerSnapshot(
                        name=layer.Name,
                        color_index=layer.Color,
                        linetype=layer.Linetype,
                        is_on=layer.LayerOn,
                        is_frozen=layer.Freeze,
                        is_locked=layer.Lock,
                        is_current=layer.current,
                    )
                    for layer in self.layer_records.values()
                    if not layer.deleted
                ),
                key=lambda item: item.name.casefold(),
            )
        )

    def inventory(self) -> tuple[LayerEntitySnapshot, ...]:
        return tuple(
            LayerEntitySnapshot(
                handle=entity.Handle,
                layer=entity.Layer,
                color_index=entity.Color,
                linetype=entity.Linetype,
                visible=entity.Visible,
                space=DrawingSpace.MODEL,
            )
            for entity in self.entities.values()
            if not entity.deleted
        )

    def layer_objects(self) -> dict[str, FakeLayer]:
        return {name: layer for name, layer in self.layer_records.items() if not layer.deleted}

    def entity_objects(self) -> dict[str, FakeEntity]:
        return {name: entity for name, entity in self.entities.items() if not entity.deleted}

    def owner_blocks(self) -> dict[str, object]:
        return {name: self.owner for name, entity in self.entities.items() if not entity.deleted}

    def sortents(self, _owner: object) -> FakeSortents:
        return self.sort_table

    @staticmethod
    def dispatch_array(entities: list[FakeEntity]) -> list[FakeEntity]:
        return entities


def install(monkeypatch: pytest.MonkeyPatch, adapter: FakeAdapter) -> None:
    monkeypatch.setattr(live, "ZWCADLiveLayer9aAdapter", lambda _name: adapter)


def test_alias_1_turns_selected_layer_off(monkeypatch: pytest.MonkeyPatch) -> None:
    adapter = FakeAdapter()
    install(monkeypatch, adapter)
    preview_request = live.LiveSelectedLayerPreviewRequest(
        document_name="Drawing1.dwg", selected_entity_handles=("E1",)
    )
    preview = live.preview_live_1(preview_request)
    request = live.LiveSelectedLayerExecuteRequest(
        **preview_request.model_dump(),
        expected_layers=preview["expected_layers"],
        expected_entities=preview["expected_entities"],
        approval_fingerprint=preview["approval_fingerprint"],
    )
    result = live.execute_live_1(request)
    assert result.changed_layers == ("A",) and adapter.layer_records["a"].LayerOn is False


def test_alias_2_isolates_without_changing_protected_layers(monkeypatch: pytest.MonkeyPatch) -> None:
    adapter = FakeAdapter()
    install(monkeypatch, adapter)
    adapter.layer_records["b"].LayerOn = True
    preview_request = live.LiveSelectedLayerPreviewRequest(
        document_name="Drawing1.dwg", selected_entity_handles=("E1",)
    )
    preview = live.preview_live_2(preview_request)
    assert "Defpoints" not in [change["layer"] for change in preview["plan"]["changes"]]
    request = live.LiveSelectedLayerExecuteRequest(
        **preview_request.model_dump(),
        expected_layers=preview["expected_layers"],
        expected_entities=preview["expected_entities"],
        approval_fingerprint=preview["approval_fingerprint"],
    )
    live.execute_live_2(request)
    assert adapter.layer_records["b"].LayerOn is False and adapter.layer_records["defpoints"].LayerOn is True


def test_alias_3_turns_layers_on(monkeypatch: pytest.MonkeyPatch) -> None:
    adapter = FakeAdapter()
    install(monkeypatch, adapter)
    preview_request = live.LiveAllLayersOnPreviewRequest(document_name="Drawing1.dwg")
    preview = live.preview_live_3(preview_request)
    request = live.LiveAllLayersOnExecuteRequest(
        **preview_request.model_dump(),
        expected_layers=preview["expected_layers"],
        expected_entities=preview["expected_entities"],
        approval_fingerprint=preview["approval_fingerprint"],
    )
    live.execute_live_3(request)
    assert adapter.layer_records["b"].LayerOn is True


def test_dol_verifies_relative_draw_order(monkeypatch: pytest.MonkeyPatch) -> None:
    adapter = FakeAdapter()
    install(monkeypatch, adapter)
    preview_request = live.LiveDolPreviewRequest(
        document_name="Drawing1.dwg", ordered_layers=("A", "B"), direction=DrawOrderDirection.FIRST_LAYER_TO_BACK
    )
    preview = live.preview_live_dol(preview_request)
    request = live.LiveDolExecuteRequest(
        **preview_request.model_dump(),
        expected_layers=preview["expected_layers"],
        expected_entities=preview["expected_entities"],
        approval_fingerprint=preview["approval_fingerprint"],
    )
    result = live.execute_live_dol(request)
    assert result.changed_handles == ("E1", "E2")
    assert [entity.Handle for entity in adapter.sort_table.order][-2:] == ["E1", "E2"]


def test_ely_erases_exact_entity_and_layer(monkeypatch: pytest.MonkeyPatch) -> None:
    adapter = FakeAdapter()
    install(monkeypatch, adapter)
    preview_request = live.LiveElyPreviewRequest(
        document_name="Drawing1.dwg",
        target_layers=("ERASE",),
        expected_entity_handles=("E3",),
        erase_layer_records=True,
    )
    preview = live.preview_live_ely(preview_request)
    request = live.LiveElyExecuteRequest(
        **preview_request.model_dump(),
        expected_layers=preview["expected_layers"],
        expected_entities=preview["expected_entities"],
        approval_fingerprint=preview["approval_fingerprint"],
    )
    result = live.execute_live_ely(request)
    assert result.erased_handles == ("E3",) and result.erased_layers == ("ERASE",)


def test_eoo_restores_hidden_entities(monkeypatch: pytest.MonkeyPatch) -> None:
    adapter = FakeAdapter()
    install(monkeypatch, adapter)
    preview_request = live.LiveEooPreviewRequest(document_name="Drawing1.dwg")
    preview = live.preview_live_eoo(preview_request)
    request = live.LiveEooExecuteRequest(
        **preview_request.model_dump(),
        expected_layers=preview["expected_layers"],
        expected_entities=preview["expected_entities"],
        approval_fingerprint=preview["approval_fingerprint"],
    )
    result = live.execute_live_eoo(request)
    assert result.changed_handles == ("E2",) and adapter.entities["e2"].Visible is True
