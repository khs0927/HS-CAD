from __future__ import annotations

import pytest

from src.adapters.zwcad_com_adapter import ZWCADCOMAdapter
from src.adapters.xicad_adapter import XiCADAdapter
from tests.integration._helpers import sample_dwg_copy, xicad_root


@pytest.mark.integration
def test_queue_xicad_wall_alias_real(tmp_path):
    dwg = sample_dwg_copy(tmp_path)
    adapter = ZWCADCOMAdapter(visible=True)
    adapter.open_document(str(dwg))
    xi = XiCADAdapter(adapter, xicad_root())
    xi.run_alias("WAL")
    adapter.close()
