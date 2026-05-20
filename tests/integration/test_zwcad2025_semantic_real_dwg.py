from __future__ import annotations

import os

import pytest

from src.adapters.zwcad_com_adapter import ZWCADCOMAdapter
from src.semantics.object_classifier import classify_objects
from tests.integration._helpers import sample_dwg_copy


@pytest.mark.integration
def test_zwcad2025_semantic_real_dwg(tmp_path):
    if os.getenv("ZWCAD_TEST_VERSION") not in {None, "", "2025"}:
        pytest.skip("ZWCAD_TEST_VERSION is not 2025")
    dwg = sample_dwg_copy(tmp_path)
    adapter = ZWCADCOMAdapter(version="2025", start_if_needed=True)
    adapter.connect()
    adapter.open_document(str(dwg))
    rows = classify_objects(adapter.scan_modelspace())
    assert isinstance(rows, list)
