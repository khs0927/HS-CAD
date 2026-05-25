from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from hscad.adapters.ezdxf_adapter import read_dxf_entities
from tests.fixtures.minimal_floorplan_factory import write_minimal_floorplan_dxf


def test_runtime_dxf_fixture_factory_and_parser(tmp_path: Path) -> None:
    fixture = write_minimal_floorplan_dxf(tmp_path / "minimal_floorplan.dxf")
    entities = read_dxf_entities(fixture)
    assert len(entities) >= 4
    assert {e.layer for e in entities} >= {"WAL1", "TEXT", "DIMLE"}


def test_review_only_cli_module_runs(tmp_path: Path) -> None:
    fixture = write_minimal_floorplan_dxf(tmp_path / "minimal_floorplan.dxf")
    out = tmp_path / "out"
    result = subprocess.run([sys.executable, "-X", "utf8", "-m", "hscad.app.cli_main_code", "--input", str(fixture), "--out", str(out)], text=True, capture_output=True, check=False)
    assert result.returncode == 0, result.stderr + result.stdout
    assert (out / "MAIN_CODE_PIPELINE_RESULT.json").exists()
    assert (out / "FINAL_REPORT.md").exists()


def test_src_main_patch_script_dry_run_is_conservative(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    (repo / "src").mkdir(parents=True)
    (repo / "src" / "main.py").write_text("from __future__ import annotations\n\ndef main() -> int:\n    return 0\n", encoding="utf-8")
    script = Path("scripts/register_main_code_cli.py")
    result = subprocess.run([sys.executable, str(script), "--repo-root", str(repo), "--dry-run"], text=True, capture_output=True, check=False)
    assert result.returncode == 0, result.stderr + result.stdout
    assert "STATUS=patched" in result.stdout
    assert "hscad-main-code-pipeline" in result.stdout
    assert "src/main.py" in result.stdout
