from __future__ import annotations

import os
import pathlib
import subprocess

import pytest


@pytest.mark.integration
def test_measure_zium_sheet_usable_area_cli_with_real_zwcad(tmp_path: pathlib.Path):
    if os.environ.get("HS_CAD_RUN_ZWCAD_TESTS") != "1":
        pytest.skip("Set HS_CAD_RUN_ZWCAD_TESTS=1 to run tests that require active ZWCAD.")

    out_dir = tmp_path / "zium_test"
    repo_root = pathlib.Path(__file__).resolve().parents[1]
    subprocess.check_call(
        [
            "python",
            "tools/measure_zium_sheet_usable_area.py",
            "--out-dir",
            str(out_dir),
        ],
        cwd=str(repo_root),
    )

    assert (out_dir / "zium_sheet_usable_area.json").is_file()
    assert (out_dir / "zium_sheet_usable_area.md").is_file()
