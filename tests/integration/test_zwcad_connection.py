from __future__ import annotations

import os
import shutil
from pathlib import Path

import pytest

from src.adapters.zwcad_com_adapter import ZWCADCOMAdapter

pytestmark = pytest.mark.integration


def _enabled() -> bool:
    return os.getenv("ZWCAD_INTEGRATION_TEST") == "1"


@pytest.mark.skipif(not _enabled(), reason="Requires ZWCAD_INTEGRATION_TEST=1 and installed ZWCAD")
def test_real_zwcad_connection_and_scan(tmp_path: Path):
    dwg = os.getenv("ZWCAD_TEST_DWG")
    assert dwg, "Set ZWCAD_TEST_DWG to a sample DWG path"
    target = tmp_path / "sample_copy.dwg"
    shutil.copy2(dwg, target)
    adapter = ZWCADCOMAdapter(visible=True)
    adapter.connect()
    adapter.open_document(str(target))
    objects = adapter.scan_modelspace()
    assert isinstance(objects, list)
