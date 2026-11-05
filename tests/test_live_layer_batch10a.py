from __future__ import annotations

import pytest

import xicad_mcp.live_layer_batch10a as live
from xicad_mcp.headless_core_batch1 import DrawingSpace
from xicad_mcp.headless_core_batch9 import (
    EntityPropertyPolicy,
    LayerEntitySnapshot,
    LayerSnapshot,
    TargetLayerMode,
    TargetLayerSpec,
)
from xicad_mcp.headless_core_batch10 import (
    ColorLayerBatchMethod,
    ColorLayerCarrier,
    ColorLayerMapping,
    ColorLayerObjectSnapshot,
    ObjectKind,
    SimilarityPolicy,
    SimilarLayerObjectSnapshot,
)


class FakeLayer:
    def __init__(self, name: str, color: int = 7, *, current: bool = False) -> None:
        self.Name, self.Color, self.Linetype = name, color, "Continuous"
        self.LayerOn, self.Freeze, self.Lock, self.current = True, False, False, current


class FakeLayers:
    def __init__(self, adapter: FakeAdapter) -> None:
        self.adapter = adapter

    def Add(self, name: str) -> FakeLayer:
        layer = FakeLayer(name)
        self.adapter.records[name.casefold()] = layer
        return layer


class FakeDoc:
    Name = "Drawing1.dwg"

    def __init__(self, adapter: FakeAdapter) -> None:
        self.Layers = FakeLayers(adapter)
        self.started = self.ended = 0

    def StartUndoMark(self) -> None:
        self.started += 1

    def EndUndoMark(self) -> None:
        self.ended += 1


class FakeEntity:
    def __init__(self, handle: str, layer: str, color: int, object_name: str = "AcDbLine") -> None:
        self.Handle, self.Layer, self.Color = handle, layer, color
        self.Linetype, self.ObjectName = "ByLayer", object_name


class FakeAdapter:
    def __init__(self) -> None:
        self.records = {
            "0": FakeLayer("0", current=True),
            "defpoints": FakeLayer("Defpoints"),
            "a": FakeLayer("A"),
            "b": FakeLayer("B"),
            "target": FakeLayer("TARGET"),
        }
        self.objects_map = {
            "e1": FakeEntity("E1", "A", 1),
            "e2": FakeEntity("E2", "B", 2),
            "t1": FakeEntity("T1", "A", 3, "AcDbText"),
        }
        self.doc = FakeDoc(self)

    def connect(self) -> FakeDoc:
        return self.doc

    def layers(self) -> tuple[LayerSnapshot, ...]:
        return tuple(
            sorted(
                (
                    LayerSnapshot(
                        name=r.Name,
                        color_index=r.Color,
                        linetype=r.Linetype,
                        is_on=r.LayerOn,
                        is_frozen=r.Freeze,
                        is_locked=r.Lock,
                        is_current=r.current,
                    )
                    for r in self.records.values()
                ),
                key=lambda x: x.name.casefold(),
            )
        )

    def inventory(self) -> tuple[LayerEntitySnapshot, ...]:
        return tuple(
            LayerEntitySnapshot(
                handle=e.Handle, layer=e.Layer, color_index=e.Color, linetype=e.Linetype, space=DrawingSpace.MODEL
            )
            for e in self.objects_map.values()
        )

    def color_inventory(self) -> tuple[ColorLayerObjectSnapshot, ...]:
        return tuple(
            ColorLayerObjectSnapshot(
                **item.model_dump(),
                carrier=(
                    ColorLayerCarrier.TEXT
                    if self.objects_map[item.handle.casefold()].ObjectName == "AcDbText"
                    else ColorLayerCarrier.GENERAL
                ),
            )
            for item in self.inventory()
        )

    def similar_inventory(self) -> tuple[SimilarLayerObjectSnapshot, ...]:
        return tuple(
            SimilarLayerObjectSnapshot(
                **item.model_dump(),
                object_kind=(
                    ObjectKind.TEXT
                    if self.objects_map[item.handle.casefold()].ObjectName == "AcDbText"
                    else ObjectKind.LINE
                ),
            )
            for item in self.inventory()
        )

    def entity_objects(self) -> dict[str, FakeEntity]:
        return self.objects_map

    def layer_objects(self) -> dict[str, FakeLayer]:
        return self.records


def install(monkeypatch: pytest.MonkeyPatch, adapter: FakeAdapter) -> None:
    monkeypatch.setattr(live, "ZWCADLiveLayer10aAdapter", lambda _name: adapter)


def test_lcd_creates_color_layer_and_moves_entity(monkeypatch: pytest.MonkeyPatch) -> None:
    adapter = FakeAdapter()
    install(monkeypatch, adapter)
    request0 = live.LiveLcdPreviewRequest(
        document_name="Drawing1.dwg",
        method=ColorLayerBatchMethod.INDIVIDUAL_MAPPING,
        mappings=(
            ColorLayerMapping(
                source_color_index=1,
                target_layer=TargetLayerSpec(
                    mode=TargetLayerMode.CREATE, name="C1", color_index=1, linetype="Continuous"
                ),
            ),
        ),
    )
    preview = live.preview_live_lcd(request0)
    request = live.LiveLcdExecuteRequest(
        **request0.model_dump(),
        expected_layers=preview["expected_layers"],
        expected_entities=preview["expected_entities"],
        approval_fingerprint=preview["approval_fingerprint"],
    )
    result = live.execute_live_lcd(request)
    assert result.created_layers == ("C1",) and adapter.objects_map["e1"].Layer == "C1"


def test_lco_changes_only_layer_and_preserves_properties(monkeypatch: pytest.MonkeyPatch) -> None:
    adapter = FakeAdapter()
    install(monkeypatch, adapter)
    request0 = live.LiveLcoPreviewRequest(document_name="Drawing1.dwg", target_handles=("E1",), target_layer="TARGET")
    preview = live.preview_live_lco(request0)
    request = live.LiveLcoExecuteRequest(
        **request0.model_dump(),
        expected_layers=preview["expected_layers"],
        expected_entities=preview["expected_entities"],
        approval_fingerprint=preview["approval_fingerprint"],
    )
    live.execute_live_lco(request)
    assert (adapter.objects_map["e1"].Layer, adapter.objects_map["e1"].Color) == ("TARGET", 1)


def test_lcs_changes_matching_object_kind(monkeypatch: pytest.MonkeyPatch) -> None:
    adapter = FakeAdapter()
    install(monkeypatch, adapter)
    request0 = live.LiveLcsPreviewRequest(
        document_name="Drawing1.dwg",
        reference_handle="E1",
        similarity_policy=SimilarityPolicy.OBJECT_KIND,
        target_layer="TARGET",
        property_policy=EntityPropertyPolicy.BY_LAYER,
    )
    preview = live.preview_live_lcs(request0)
    request = live.LiveLcsExecuteRequest(
        **request0.model_dump(),
        expected_layers=preview["expected_layers"],
        expected_entities=preview["expected_entities"],
        approval_fingerprint=preview["approval_fingerprint"],
    )
    result = live.execute_live_lcs(request)
    assert result.changed_handles == ("E1", "E2")
    assert adapter.objects_map["t1"].Layer == "A"


@pytest.mark.parametrize("alias", ["lf", "lff", "lfk"])
def test_layer_protection_commands(monkeypatch: pytest.MonkeyPatch, alias: str) -> None:
    adapter = FakeAdapter()
    install(monkeypatch, adapter)
    request0 = live.LiveLayerSetPreviewRequest(document_name="Drawing1.dwg", selected_entity_handles=("E1",))
    preview = getattr(live, f"preview_live_{alias}")(request0)
    request = live.LiveLayerSetExecuteRequest(
        **request0.model_dump(),
        expected_layers=preview["expected_layers"],
        expected_entities=preview["expected_entities"],
        approval_fingerprint=preview["approval_fingerprint"],
    )
    result = getattr(live, f"execute_live_{alias}")(request)
    assert result.postcondition_verified is True
    assert adapter.records["0"].Freeze is False and adapter.records["defpoints"].Freeze is False


def test_system_layer_source_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    adapter = FakeAdapter()
    adapter.objects_map["e1"].Layer = "0"
    install(monkeypatch, adapter)
    request = live.LiveLcoPreviewRequest(document_name="Drawing1.dwg", target_handles=("E1",), target_layer="TARGET")
    with pytest.raises(ValueError, match="system-layer"):
        live.preview_live_lco(request)
