from __future__ import annotations

import importlib
import sys


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
