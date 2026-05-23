from __future__ import annotations

import importlib
import sys

import pytest


def test_cad_adapter_modules_do_not_import_app_logger_at_module_load():
    """CAD adapters should stay import-safe in pytest collection and --help paths.

    The adapters may need app logging when a COM/XiCAD action actually runs, but
    importing the modules must not pull in src.app.logger. Keeping the logger
    imports inside methods prevents src.app / src.app.cli / adapter circular
    imports when CLI modules are registered from src.main.
    """
    for module_name in (
        "src.adapters.zwcad_com_adapter",
        "src.adapters.xicad_adapter",
    ):
        sys.modules.pop(module_name, None)
    sys.modules.pop("src.app.logger", None)

    importlib.import_module("src.adapters.zwcad_com_adapter")
    importlib.import_module("src.adapters.xicad_adapter")

    assert "src.app.logger" not in sys.modules


def test_main_skips_absent_optional_cli_module():
    main = importlib.import_module("src.main")

    assert main._register_cli_module("src.app.__definitely_missing_cli__") is False


def test_main_does_not_hide_dependency_import_errors(monkeypatch):
    main = importlib.import_module("src.main")
    real_import_module = importlib.import_module

    def fake_import_module(module_name: str):
        if module_name == "src.app.fake_existing_cli":
            raise ModuleNotFoundError("No module named 'missing_dependency'", name="missing_dependency")
        return real_import_module(module_name)

    monkeypatch.setattr(importlib, "import_module", fake_import_module)

    with pytest.raises(ModuleNotFoundError) as exc_info:
        main._register_cli_module("src.app.fake_existing_cli")

    assert exc_info.value.name == "missing_dependency"
