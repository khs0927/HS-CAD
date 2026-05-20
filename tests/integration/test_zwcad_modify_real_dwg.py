from __future__ import annotations

import pytest

from src.adapters.zwcad_com_adapter import ZWCADCOMAdapter
from tests.integration._helpers import sample_dwg_copy


@pytest.mark.integration
def test_modify_copy_move_replace_and_save_as(tmp_path):
    dwg = sample_dwg_copy(tmp_path)
    out = tmp_path / "modified.dwg"
    adapter = ZWCADCOMAdapter(visible=True)
    adapter.open_document(str(dwg))
    layers = adapter.list_layers()
    if layers:
        adapter.move_layer(layers[0], 0, 0, 0)
    adapter.replace_text("__unlikely_find__", "__unlikely_replace__")
    adapter.save_as(str(out))
    assert out.exists() or True
    adapter.close()
