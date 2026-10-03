"""Host-free checks: dependency import cannot promote a placeholder adapter."""
import sys
from types import ModuleType

import pytest

from src.adapters.pyrx_adapter import PyRxAdapter


def test_reporting_does_not_import_or_contact_host(monkeypatch):
    monkeypatch.setitem(sys.modules, "pyrx", None)
    adapter = PyRxAdapter()
    assert adapter.health()["dependency_loaded"] is False
    assert adapter.health()["execution_allowed"] is False
    assert not any(adapter.capabilities().values())


def test_successful_import_does_not_grant_native_readiness(monkeypatch):
    monkeypatch.setitem(sys.modules, "pyrx", ModuleType("pyrx"))
    adapter = PyRxAdapter()
    adapter.connect()
    report = adapter.health()
    assert report["dependency_loaded"] is True
    assert report["status"] == "NOT_IMPLEMENTED"
    for key in ("host_verified", "read_ready", "write_ready", "execution_allowed"):
        assert report[key] is False
    assert not any(adapter.capabilities().values())
    with pytest.raises(NotImplementedError):
        adapter.get_active_document()
    adapter.close()
    assert adapter.health()["dependency_loaded"] is False


def test_failed_reconnect_clears_previous_dependency_state(monkeypatch):
    adapter = PyRxAdapter()
    monkeypatch.setitem(sys.modules, "pyrx", ModuleType("pyrx"))
    adapter.connect()
    monkeypatch.setitem(sys.modules, "pyrx", None)
    with pytest.raises(NotImplementedError):
        adapter.connect()
    assert adapter.health()["dependency_loaded"] is False
