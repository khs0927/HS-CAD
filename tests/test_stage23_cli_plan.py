import json
import subprocess
import sys
from pathlib import Path


def test_build_style_context_cli(tmp_path: Path):
    out = tmp_path / "style"
    subprocess.check_call(
        [sys.executable, "-m", "src.neuro_seq_cad_bridge.cli", "build-style-context", "--out", str(out)]
    )
    assert (out / "style_context.json").exists()
    assert (out / "style_context.md").exists()


def test_run_all_preview_plan_cli_with_missing_inputs(tmp_path: Path):
    out = tmp_path / "bridge"
    subprocess.check_call(
        [sys.executable, "-m", "src.neuro_seq_cad_bridge.cli", "run-all-preview-plan", "--out", str(out)]
    )
    assert (out / "preview_insert_plan.json").exists()
    data = json.loads((out / "preview_insert_plan.json").read_text(encoding="utf-8"))
    assert data["save"] is False
    assert data["can_execute"] is False
