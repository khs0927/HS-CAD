from __future__ import annotations

import os

import pytest

from src.integrations.xicad_paths import detect_xicad_profile
from tests.integration._helpers import xicad_root


@pytest.mark.integration
def test_xicad_zwcad2026_detection():
    if os.getenv("ZWCAD_TEST_VERSION") not in {None, "", "2026"}:
        pytest.skip("ZWCAD_TEST_VERSION is not 2026")
    profile = detect_xicad_profile(xicad_root())
    assert profile.root.exists()
