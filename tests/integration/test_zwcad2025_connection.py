from __future__ import annotations

import os

import pytest

from src.adapters.zwcad_com_adapter import ZWCADCOMAdapter


@pytest.mark.integration
def test_zwcad2025_connection():
    if os.getenv("ZWCAD_TEST_VERSION") not in {None, "", "2025"}:
        pytest.skip("ZWCAD_TEST_VERSION is not 2025")
    adapter = ZWCADCOMAdapter(version="2025", start_if_needed=True)
    adapter.connect()
    assert adapter.app is not None
    assert adapter.active_progid
