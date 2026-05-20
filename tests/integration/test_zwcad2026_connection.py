from __future__ import annotations

import os

import pytest

from src.adapters.zwcad_com_adapter import ZWCADCOMAdapter


@pytest.mark.integration
def test_zwcad2026_connection():
    if os.getenv("ZWCAD_TEST_VERSION") not in {None, "", "2026"}:
        pytest.skip("ZWCAD_TEST_VERSION is not 2026")
    adapter = ZWCADCOMAdapter(version="2026", start_if_needed=True)
    adapter.connect()
    assert adapter.app is not None
    assert adapter.active_progid
