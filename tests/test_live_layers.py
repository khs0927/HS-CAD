from __future__ import annotations

from typing import Any

import pytest
from pydantic import ValidationError

from xicad_mcp.headless_core_batch1 import LayerAffixMode
from xicad_mcp.live_layers import (
    LiveLayerAffixExecuteRequest,
    LiveLayerAffixPreviewRequest,
    execute_live_lpp,
    execute_live_lps,
    preview_live_layer_affix,
)


class FakeLayer:
    def __init__(self, name: str) -> None:
        self.Name = name


class FailingLayer:
    def __init__(self, name: str) -> None:
        self._name = name

    @property
    def Name(self) -> str:
        return self._name

    @Name.setter
    def Name(self, _value: str) -> None:
        raise RuntimeError("COM rename failed")


class FakeDocument:
    def __init__(self, *names: str) -> None:
        self.Name = "Drawing1.dwg"
        self.Layers = [FakeLayer(name) for name in names]
        self.events: list[str] = []

    def StartUndoMark(self) -> None:
        self.events.append("start")

    def EndUndoMark(self) -> None:
        self.events.append("end")


def request(mode: LayerAffixMode = LayerAffixMode.PREFIX) -> LiveLayerAffixPreviewRequest:
    return LiveLayerAffixPreviewRequest(
        document_name="Drawing1.dwg",
        mode=mode,
        affix="MCP_" if mode is LayerAffixMode.PREFIX else "_MCP",
        target_names=("Walls",),
    )


def approved(preview: dict[str, Any]) -> LiveLayerAffixExecuteRequest:
    return LiveLayerAffixExecuteRequest(
        document_name=preview["document_name"],
        mode=preview["mode"],
        affix=preview["affix"],
        target_names=preview["target_names"],
        expected_rename_pairs=preview["expected_rename_pairs"],
        approval_fingerprint=preview["approval_fingerprint"],
    )


@pytest.mark.parametrize("name", ["0", "Defpoints", "xref|Walls"])
def test_protected_and_xref_targets_are_forbidden(name: str) -> None:
    with pytest.raises(ValidationError, match="cannot be renamed"):
        LiveLayerAffixPreviewRequest(
            document_name="Drawing1.dwg",
            mode=LayerAffixMode.PREFIX,
            affix="MCP_",
            target_names=(name,),
        )


def test_preview_binds_fingerprint_to_resolved_rename(monkeypatch: pytest.MonkeyPatch) -> None:
    doc = FakeDocument("0", "Defpoints", "Walls")
    monkeypatch.setattr("xicad_mcp.live_layers._drawing", lambda _name: doc)
    preview = preview_live_layer_affix(request())

    execution = approved(preview)
    assert preview["command_alias"] == "LPP"
    assert preview["expected_rename_pairs"] == [{"source": "Walls", "target": "MCP_Walls"}]
    assert execution.approval_fingerprint == execution.expected_fingerprint()


def test_preview_rejects_collision(monkeypatch: pytest.MonkeyPatch) -> None:
    doc = FakeDocument("0", "Walls", "MCP_Walls")
    monkeypatch.setattr("xicad_mcp.live_layers._drawing", lambda _name: doc)
    with pytest.raises(ValueError, match="collision"):
        preview_live_layer_affix(request())


def test_lpp_executes_inside_undo_mark_and_returns_evidence(monkeypatch: pytest.MonkeyPatch) -> None:
    doc = FakeDocument("0", "Defpoints", "Walls")
    monkeypatch.setattr("xicad_mcp.live_layers._drawing", lambda _name: doc)
    execution = approved(preview_live_layer_affix(request()))

    result = execute_live_lpp(execution)

    assert doc.events == ["start", "end"]
    assert [layer.Name for layer in doc.Layers] == ["0", "Defpoints", "MCP_Walls"]
    assert result.command_alias == "LPP"
    assert result.postcondition_verified is True
    assert result.evidence[0].source_absent is True
    assert result.evidence[0].target_present is True


def test_lps_executes_suffix_plan(monkeypatch: pytest.MonkeyPatch) -> None:
    doc = FakeDocument("0", "Walls")
    monkeypatch.setattr("xicad_mcp.live_layers._drawing", lambda _name: doc)
    execution = approved(preview_live_layer_affix(request(LayerAffixMode.SUFFIX)))

    result = execute_live_lps(execution)

    assert result.command_alias == "LPS"
    assert doc.Layers[1].Name == "Walls_MCP"


def test_executor_rejects_wrong_command_before_cad_connection(monkeypatch: pytest.MonkeyPatch) -> None:
    doc = FakeDocument("0", "Walls")
    monkeypatch.setattr("xicad_mcp.live_layers._drawing", lambda _name: doc)
    execution = approved(preview_live_layer_affix(request()))
    monkeypatch.setattr(
        "xicad_mcp.live_layers._drawing",
        lambda _name: pytest.fail("CAD must not be contacted for wrong command"),
    )

    with pytest.raises(ValueError, match="only executes LPS"):
        execute_live_lps(execution)


def test_executor_rejects_layer_inventory_drift_before_mutation(monkeypatch: pytest.MonkeyPatch) -> None:
    doc = FakeDocument("0", "Walls")
    monkeypatch.setattr("xicad_mcp.live_layers._drawing", lambda _name: doc)
    execution = approved(preview_live_layer_affix(request()))
    doc.Layers[1].Name = "Changed"

    with pytest.raises(ValueError, match="layer not found"):
        execute_live_lpp(execution)
    assert doc.events == []


def test_executor_rejects_tampered_fingerprint_before_cad_connection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    preview_request = request()
    execution = LiveLayerAffixExecuteRequest(
        **preview_request.model_dump(),
        expected_rename_pairs=({"source": "Walls", "target": "MCP_Walls"},),
        approval_fingerprint="sha256:" + "0" * 64,
    )
    monkeypatch.setattr(
        "xicad_mcp.live_layers._drawing",
        lambda _name: pytest.fail("CAD must not be contacted for invalid approval"),
    )

    with pytest.raises(ValueError, match="fingerprint"):
        execute_live_lpp(execution)


def test_undo_mark_is_closed_when_com_rename_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    doc = FakeDocument("0", "Walls")
    monkeypatch.setattr("xicad_mcp.live_layers._drawing", lambda _name: doc)
    execution = approved(preview_live_layer_affix(request()))
    doc.Layers[1] = FailingLayer("Walls")

    with pytest.raises(RuntimeError, match="COM rename failed"):
        execute_live_lpp(execution)
    assert doc.events == ["start", "end"]
