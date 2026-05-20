from __future__ import annotations

import pytest

from src.adapters.zwcad_com_adapter import ZWCADCOMAdapter
from tests.integration._helpers import sample_dwg_copy


@pytest.mark.integration
def test_scan_real_dwg_layers_blocks_texts(tmp_path):
    dwg = sample_dwg_copy(tmp_path)
    adapter = ZWCADCOMAdapter(visible=True)
    adapter.open_document(str(dwg))
    objects = adapter.scan_modelspace()
    assert isinstance(objects, list)
    assert isinstance(adapter.list_layers(), list)
    assert isinstance(adapter.list_blocks(), list)
    assert isinstance(adapter.list_texts(), list)
    adapter.close()
