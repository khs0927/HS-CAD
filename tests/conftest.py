from __future__ import annotations

import os
import pytest


def pytest_addoption(parser):
    parser.addoption("--run-integration", action="store_true", default=False, help="run real ZWCAD integration tests")


def pytest_configure(config):
    config.addinivalue_line("markers", "integration: real ZWCAD/XiCAD integration test")


def pytest_collection_modifyitems(config, items):
    enabled = config.getoption("--run-integration") or os.getenv("ZWCAD_INTEGRATION_TEST") == "1"
    if enabled:
        return
    skip = pytest.mark.skip(reason="requires --run-integration or ZWCAD_INTEGRATION_TEST=1")
    for item in items:
        if "integration" in item.keywords:
            item.add_marker(skip)
