from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path

import pytest

from src.adapters.zwcad_com_adapter import ZWCADCOMAdapter
from src.testing import environment_check

ROOT = Path(__file__).resolve().parents[1]


class _FakeApp:
    Name = "ZWCAD"
    Version = "2026"
    ActiveDocument = types.SimpleNamespace(Name="virtual.dwg")
    Visible = False


def _load_orchestrator():
    path = ROOT / "scripts" / "run_plugin_orchestrator.py"
    spec = importlib.util.spec_from_file_location("hscad_run_plugin_orchestrator_virtual", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _install_com_modules(monkeypatch: pytest.MonkeyPatch, *, active=None, created=None) -> None:
    def _active(_progid: str):
        if isinstance(active, BaseException) or active is None:
            raise RuntimeError("no active object")
        return active

    def _created(_progid: str):
        if isinstance(created, BaseException) or created is None:
            raise RuntimeError("cannot create object")
        return created

    win32_parent = types.ModuleType("win32com")
    win32_client = types.ModuleType("win32com.client")
    win32_client.GetActiveObject = _active
    win32_client.Dispatch = _created
    win32_parent.client = win32_client
    comtypes_parent = types.ModuleType("comtypes")
    comtypes_client = types.ModuleType("comtypes.client")
    comtypes_client.GetActiveObject = _active
    comtypes_client.CreateObject = _created
    comtypes_parent.client = comtypes_client
    monkeypatch.setitem(sys.modules, "win32com", win32_parent)
    monkeypatch.setitem(sys.modules, "win32com.client", win32_client)
    monkeypatch.setitem(sys.modules, "comtypes", comtypes_parent)
    monkeypatch.setitem(sys.modules, "comtypes.client", comtypes_client)


def test_environment_probe_simulates_windows_active_object(monkeypatch: pytest.MonkeyPatch):
    app = _FakeApp()
    monkeypatch.setattr(environment_check.platform, "system", lambda: "Windows")
    monkeypatch.setattr(environment_check, "_try_get_active", lambda _progid: (app, {"ok": True, "method": "GetActiveObject"}))
    result = environment_check.probe_zwcad_com(version="2026", start_zwcad=False)
    assert result["connected"] is True
    assert result["active_document"] == "virtual.dwg"


def test_environment_probe_balances_com_lifecycle(monkeypatch: pytest.MonkeyPatch):
    token = ("fake", object())
    events: list[tuple[str, object]] = []
    monkeypatch.setattr(environment_check.platform, "system", lambda: "Windows")
    monkeypatch.setattr(environment_check, "_initialize_com", lambda: token)
    monkeypatch.setattr(environment_check, "_uninitialize_com", lambda value: events.append(value))
    monkeypatch.setattr(environment_check, "_try_get_active", lambda _progid: (_FakeApp(), {"ok": True}))
    assert environment_check.probe_zwcad_com(version="2026")["connected"] is True
    assert events == [token]


def test_environment_probe_failure_does_not_false_pass(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(environment_check.platform, "system", lambda: "Windows")
    monkeypatch.setattr(environment_check, "_try_get_active", lambda _progid: (None, {"ok": False}))
    result = environment_check.probe_zwcad_com(version="2026", start_zwcad=False)
    assert result["connected"] is False
    assert result["connection_mode"] == "failed"


def test_adapter_uses_active_object_before_create(monkeypatch: pytest.MonkeyPatch):
    app = _FakeApp()
    _install_com_modules(monkeypatch, active=app, created=RuntimeError("must not create"))
    adapter = ZWCADCOMAdapter(version="2026", start_if_needed=True)
    adapter.connect()
    assert adapter.app is app


def test_adapter_falls_back_to_create_object(monkeypatch: pytest.MonkeyPatch):
    app = _FakeApp()
    _install_com_modules(monkeypatch, active=RuntimeError("not running"), created=app)
    adapter = ZWCADCOMAdapter(version="2026", start_if_needed=True)
    adapter.connect()
    assert adapter.app is app
    assert app.Visible is True


def test_adapter_refuses_spawn_when_disabled(monkeypatch: pytest.MonkeyPatch):
    _install_com_modules(monkeypatch, active=RuntimeError("not running"), created=RuntimeError("spawn disabled"))
    with pytest.raises(RuntimeError, match="start_if_needed=False"):
        ZWCADCOMAdapter(version="2026", start_if_needed=False).connect()


def test_orchestrator_blocks_windows_check_on_non_windows(monkeypatch: pytest.MonkeyPatch):
    orchestrator = _load_orchestrator()
    check = orchestrator.Check(name="virtual-windows-block", command=(sys.executable, "-c", "raise SystemExit(99)"), platforms=("Windows",))
    monkeypatch.setattr(orchestrator.platform, "system", lambda: "Linux")
    monkeypatch.setattr(orchestrator.subprocess, "run", lambda *args, **kwargs: pytest.fail("must not run"))
    result = orchestrator.run_check(check, timeout=10, fixture_root=None, include_logs=False)
    assert result.status == "blocked"


def test_orchestrator_simulates_windows_pass(monkeypatch: pytest.MonkeyPatch):
    orchestrator = _load_orchestrator()
    check = orchestrator.Check(name="virtual-windows-pass", command=(sys.executable, "-c", "print('simulated-windows-ok')"), platforms=("Windows",))
    monkeypatch.setattr(orchestrator.platform, "system", lambda: "Windows")
    result = orchestrator.run_check(check, timeout=10, fixture_root=None, include_logs=True)
    assert result.status == "passed"


def test_windows_profile_selects_strict_fixture_script(tmp_path: Path):
    orchestrator = _load_orchestrator()
    profiles, checks = orchestrator.build_checks(["windows-cad"], str(tmp_path))
    assert profiles == ["windows-cad"]
    assert checks[0].platforms == ("Windows",)
    assert "run_windows_drawing_index_fixture_matrix.ps1" in checks[0].command
