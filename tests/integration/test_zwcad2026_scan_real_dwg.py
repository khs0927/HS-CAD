from __future__ import annotations

import os

import pytest

from src.adapters.zwcad_com_adapter import ZWCADCOMAdapter
from tests.integration._helpers import sample_dwg_copy


@pytest.mark.integration
def test_zwcad2026_scan_real_dwg(tmp_path):
    if os.getenv("ZWCAD_TEST_VERSION") not in {None, "", "2026"}:
        pytest.skip("ZWCAD_TEST_VERSION is not 2026")
    dwg = sample_dwg_copy(tmp_path)
    adapter = ZWCADCOMAdapter(version="2026", start_if_needed=True)
    adapter.connect()
    adapter.open_document(str(dwg))
    assert isinstance(adapter.scan_modelspace(), list)
