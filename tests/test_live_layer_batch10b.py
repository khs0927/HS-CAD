from __future__ import annotations

from typing import Any

import pytest

from tests.test_live_layer_batch9b import FakeDocument
from xicad_mcp.headless_core_batch1 import Point3D
from xicad_mcp.headless_core_batch10 import (
    ActivateLayersRequest,
    ColorLayerStateRequest,
    ColorSource,
    LayerListDestination,
    LayerListRequest,
    LayerPropertyMode,
    LayerPropertyPatch,
    LayerPropertyRequest,
    LayerSetRequest,
)
from xicad_mcp.live_layer_batch10b import (
    LiveColorStateExecuteRequest,
    LiveLkExecuteRequest,
    LiveLosExecuteRequest,
    LiveLpExecuteRequest,
    execute_live_lk,
    execute_live_llc,
    execute_live_loc,
    execute_live_los,
    execute_live_lp,
    preview_live_lk,
    preview_live_llc,
    preview_live_loc,
    preview_live_los,
    preview_live_lp,
    read_live_lst,
)


@pytest.fixture
def doc(monkeypatch: pytest.MonkeyPatch) -> FakeDocument:
    value = FakeDocument()
    for layer in value.Layers:
        layer.Plottable = True
    monkeypatch.setattr("xicad_mcp.live_layer_batch10b._drawing", lambda _name: value)
    monkeypatch.setattr("xicad_mcp.live_layer_batch9b._drawing", lambda _name: value)
    return value


def values(preview: dict[str, Any]) -> dict[str, Any]:
    return {
        "request": preview["request"],
        "expected_layers": preview["expected_layers"],
        "expected_entities": preview["expected_entities"],
        "approval_fingerprint": preview["approval_fingerprint"],
    }


def test_lk_locks_selected_entity_layer(doc: FakeDocument) -> None:
    preview = preview_live_lk(
        LayerSetRequest(document_id=doc.Name, selected_entity_handles=("A",))
    )
    result = execute_live_lk(LiveLkExecuteRequest(**values(preview)))
    assert doc.Layers.Item("OLD").Lock is True
    assert result.changed_layers == ("OLD",)
    assert doc.events == ["start", "end"]


@pytest.mark.parametrize("alias", ["LLC", "LOC"])
def test_llc_and_loc_apply_color_derived_layer_state(doc: FakeDocument, alias: str) -> None:
    request = ColorLayerStateRequest(
        document_id=doc.Name,
        color_indices=(3,),
        color_source=ColorSource.ENTITY_COLOR,
    )
    preview = preview_live_llc(request) if alias == "LLC" else preview_live_loc(request)
    execution = LiveColorStateExecuteRequest(command_alias=alias, **values(preview))
    result = execute_live_llc(execution) if alias == "LLC" else execute_live_loc(execution)
    assert doc.Layers.Item("OLD").LayerOn is (alias == "LOC")
    assert result.postcondition_verified


def test_los_activates_off_frozen_locked_layer(doc: FakeDocument) -> None:
    old = doc.Layers.Item("OLD")
    old.LayerOn = False
    old.Freeze = True
    old.Lock = True
    preview = preview_live_los(
        ActivateLayersRequest(
            document_id=doc.Name,
            target_layers=("OLD",),
            turn_on=True,
            thaw=True,
            unlock=True,
        )
    )
    result = execute_live_los(LiveLosExecuteRequest(**values(preview)))
    assert (old.LayerOn, old.Freeze, old.Lock) == (True, False, False)
    assert result.changed_layers == ("OLD",)


def test_lp_applies_layer_patch_with_exact_postcondition(doc: FakeDocument) -> None:
    request = LayerPropertyRequest(
        document_id=doc.Name,
        target_layers=("OLD",),
        patch=LayerPropertyPatch(color_index=2, plottable=False),
        mode=LayerPropertyMode.LAYER_ONLY,
    )
    preview = preview_live_lp(request)
    result = execute_live_lp(LiveLpExecuteRequest(**values(preview)))
    old = doc.Layers.Item("OLD")
    assert (old.Color, old.Plottable) == (2, False)
    assert result.changed_layers == ("OLD",)


def test_lp_converts_entity_properties_to_bylayer(doc: FakeDocument) -> None:
    request = LayerPropertyRequest(
        document_id=doc.Name,
        target_layers=("OLD",),
        mode=LayerPropertyMode.TO_BY_LAYER,
        change_entity_color=True,
        change_entity_linetype=True,
    )
    preview = preview_live_lp(request)
    result = execute_live_lp(LiveLpExecuteRequest(**values(preview)))
    assert [(item.Color, item.Linetype) for item in doc.Blocks[0].entities[:2]] == [
        (256, "ByLayer"),
        (256, "ByLayer"),
    ]
    assert result.changed_handles == ("A", "B")


def test_lp_viewport_freeze_is_truthfully_blocked(doc: FakeDocument) -> None:
    request = LayerPropertyRequest(
        document_id=doc.Name,
        target_layers=("OLD",),
        patch=LayerPropertyPatch(viewport_frozen=True),
        mode=LayerPropertyMode.LAYER_ONLY,
    )
    with pytest.raises(ValueError, match="viewport"):
        preview_live_lp(request)


def test_lst_return_only_is_live_cad_free_output(doc: FakeDocument) -> None:
    result = read_live_lst(
        LayerListRequest(
            document_id=doc.Name,
            destination=LayerListDestination.RETURN_ONLY,
            include_properties=False,
        )
    )
    assert result.plan.rendered_lines == ("0", "NEW", "OLD")
    assert result.production_usable is True


def test_lst_drawing_destination_is_blocked_without_style_contract(doc: FakeDocument) -> None:
    request = LayerListRequest(
        document_id=doc.Name,
        destination=LayerListDestination.TEXT,
        insertion_point=Point3D(x=0, y=0),
    )
    with pytest.raises(ValueError, match="style and sizing"):
        read_live_lst(request)


def test_inventory_drift_rejected_before_undo(doc: FakeDocument) -> None:
    preview = preview_live_lk(
        LayerSetRequest(document_id=doc.Name, selected_entity_handles=("A",))
    )
    execution = LiveLkExecuteRequest(**values(preview))
    doc.Blocks[0].entities[0].Color = 9
    with pytest.raises(ValueError, match="inventory"):
        execute_live_lk(execution)
    assert doc.events == []
