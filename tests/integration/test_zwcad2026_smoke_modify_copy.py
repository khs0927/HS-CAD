from __future__ import annotations

import os

import pytest

from src.adapters.zwcad_com_adapter import ZWCADCOMAdapter
from tests.integration._helpers import sample_dwg_copy


@pytest.mark.integration
def test_zwcad2026_smoke_modify_copy(tmp_path):
    if os.getenv("ZWCAD_TEST_VERSION") not in {None, "", "2026"}:
        pytest.skip("ZWCAD_TEST_VERSION is not 2026")
    dwg = sample_dwg_copy(tmp_path)
    save_as = tmp_path / "smoke_modified.dwg"
    adapter = ZWCADCOMAdapter(version="2026", start_if_needed=True)
    adapter.connect()
    adapter.open_document(str(dwg))
    adapter.move_layer("MARK", 0, 0, 0)
    adapter.save_as(str(save_as))
    assert save_as.exists()
