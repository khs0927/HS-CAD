from __future__ import annotations

import os
import shutil
from pathlib import Path

import pytest


def sample_dwg_copy(tmp_path: Path) -> Path:
    source = os.getenv("ZWCAD_TEST_DWG")
    if not source:
        pytest.skip("ZWCAD_TEST_DWG is required")
    src = Path(source)
    if not src.exists():
        pytest.skip(f"ZWCAD_TEST_DWG does not exist: {src}")
    dst = tmp_path / src.name
    shutil.copy2(src, dst)
    return dst


def xicad_root() -> str:
    root = os.getenv("XICAD_ROOT")
    if not root:
        pytest.skip("XICAD_ROOT is required")
    return root
