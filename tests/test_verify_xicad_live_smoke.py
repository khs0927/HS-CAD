from __future__ import annotations

from dataclasses import dataclass

import pytest

from scripts.verify_xicad_live_smoke import (
    DOCUMENT_NAME,
    SCENARIOS,
    SmokeVerificationError,
    _cleanup_direct,
    _exact_document,
    _layer_exists,
    _model_handles,
    _result,
    _same_point,
    _scenario_origin,
    _selected_scenarios,
    _undo_and_wait,
    _wait_for,
)


@dataclass
class FakeDocument:
    Name: str


@dataclass
class FakeApplication:
    Documents: list[FakeDocument]


def test_exact_document_requires_one_case_exact_drawing1() -> None:
    expected = FakeDocument(DOCUMENT_NAME)
    assert _exact_document(FakeApplication([expected])) is expected
    with pytest.raises(SmokeVerificationError, match="exactly one"):
        _exact_document(FakeApplication([]))
    with pytest.raises(SmokeVerificationError, match="exactly one"):
        _exact_document(FakeApplication([expected, FakeDocument("DRAWING1.DWG")]))
    with pytest.raises(SmokeVerificationError, match="must be exactly"):
        _exact_document(FakeApplication([FakeDocument("DRAWING1.DWG")]))


def test_scenario_selection_is_ordered_unique_and_rejects_unknown() -> None:
    assert SCENARIOS == ("ct", "dts", "flt", "sol", "tb", "tbt", "rr")
    assert _selected_scenarios(("flt", "ct", "flt")) == ("flt", "ct")
    with pytest.raises(ValueError, match="unknown"):
        _selected_scenarios(("ct", "unsupported"))
    with pytest.raises(ValueError, match="at least one"):
        _selected_scenarios(())


def test_scenario_origin_rejects_empty_drawing_extents_sentinel() -> None:
    class ExtentsDocument:
        def __init__(self, maximum: tuple[float, float, float]) -> None:
            self.maximum = maximum

        def GetVariable(self, name: str) -> tuple[float, float, float]:
            assert name == "EXTMAX"
            return self.maximum

    assert _scenario_origin(ExtentsDocument((1.0e20, 1.0e20, 0.0)), 0) == (10_000.0, 10_000.0)
    assert _scenario_origin(ExtentsDocument((125.0, 250.0, 0.0)), 2) == (14_125.0, 14_250.0)


def test_wait_for_uses_injected_clock_and_times_out_deterministically() -> None:
    ticks = iter((0.0, 0.1, 0.2, 0.3))
    calls: list[float] = []
    with pytest.raises(SmokeVerificationError, match="timed out"):
        _wait_for(
            lambda: False,
            timeout=0.2,
            interval=0.1,
            clock=lambda: next(ticks),
            sleeper=calls.append,
        )
    assert calls == [0.1]


def test_wait_for_returns_when_postcondition_becomes_true() -> None:
    states = iter((False, False, True))
    sleeps: list[float] = []
    _wait_for(
        lambda: next(states),
        timeout=2.0,
        clock=lambda: 0.0,
        sleeper=sleeps.append,
    )
    assert sleeps == [0.1, 0.1]


def test_geometry_tolerance_and_passed_result_require_handle_restoration() -> None:
    assert _same_point((1.0, 2.0, 3.0), (1.0 + 1e-9, 2.0, 3.0))
    assert not _same_point((1.0, 2.0, 3.0), (1.1, 2.0, 3.0))
    passed = _result("CT", "TEMP", {"a", "b"}, {"b", "a"}, evidence=True)
    assert passed["status"] == "passed"
    assert passed["undo_restored"] is True
    assert passed["handles_restored"] is True
    assert passed["evidence"] is True
    failed_restore = _result("CT", "TEMP", {"a"}, {"b"})
    assert failed_restore["undo_restored"] is False


class FakeEntity:
    def __init__(self, handle: str) -> None:
        self.Handle = handle


class FakeLayers:
    def __init__(self, names: set[str]) -> None:
        self.names = names

    def Item(self, name: str) -> object:
        if name not in self.names:
            raise KeyError(name)
        return object()


class FakeComDocument:
    def __init__(self) -> None:
        self.ModelSpace = [FakeEntity("A"), FakeEntity("b")]
        self.Layers = FakeLayers({"TEMP"})
        self.commands: list[str] = []
        self.undo_complete = False

    def GetVariable(self, name: str) -> int:
        assert name == "CMDACTIVE"
        return 0

    def SendCommand(self, command: str) -> None:
        self.commands.append(command)
        self.undo_complete = True


def test_fake_com_handle_layer_and_undo_protocol() -> None:
    doc = FakeComDocument()
    assert _model_handles(doc) == {"a", "b"}
    assert _layer_exists(doc, "TEMP")
    assert not _layer_exists(doc, "MISSING")
    _undo_and_wait(doc, lambda: doc.undo_complete, timeout=0.1)
    assert doc.commands == ["_.UNDO\n1\n"]


class DeletableEntity(FakeEntity):
    def __init__(self, handle: str, layer: str) -> None:
        super().__init__(handle)
        self.Layer = layer
        self.deleted = False

    def Delete(self) -> None:
        self.deleted = True


class DeletableLayer:
    def __init__(self, owner: DeletableLayers, name: str) -> None:
        self.owner = owner
        self.name = name

    def Delete(self) -> None:
        self.owner.names.remove(self.name)


class DeletableLayers(FakeLayers):
    def Item(self, name: str) -> DeletableLayer:
        if name not in self.names:
            raise KeyError(name)
        return DeletableLayer(self, name)


def test_failure_cleanup_is_strictly_scoped_to_unique_smoke_layer() -> None:
    smoke = DeletableEntity("S", "HSCAD_XICAD_SMOKE_SOL_123")
    user = DeletableEntity("U", "USER")
    doc = FakeComDocument()
    doc.ModelSpace = [smoke, user]
    doc.Layers = DeletableLayers({"HSCAD_XICAD_SMOKE_SOL_123", "USER"})
    doc.Regen = lambda _mode: None
    _cleanup_direct(doc, "HSCAD_XICAD_SMOKE_SOL_123")
    assert smoke.deleted is True
    assert user.deleted is False
    assert doc.Layers.names == {"USER"}
