import json
import subprocess
import pathlib
import os

def test_sample_style_near_handle(tmp_path: pathlib.Path):
    out_dir = tmp_path / "style_test"
    # Ensure the output directory does not exist beforehand
    if out_dir.exists():
        # Cleanup just in case
        for f in out_dir.iterdir():
            f.unlink()
        out_dir.rmdir()
    # Run the tool
    repo_root = pathlib.Path(__file__).resolve().parents[1]
    subprocess.check_call([
        "python",
        "tools/sample_style_near_handle.py",
        "--handle",
        "TESTHANDLE",
        "--radius",
        "100",
        "--out-dir",
        str(out_dir),
    ], cwd=str(repo_root))

    json_path = out_dir / "local_style_sample.json"
    assert json_path.is_file()
    data = json.load(json_path.open(encoding="utf-8"))
    assert data["source_handle"] == "TESTHANDLE"
    # Verify expected keys exist
    for key in ["dominant_layers", "dominant_entity_types", "recommended_generation_style"]:
        assert key in data
    rec = data["recommended_generation_style"]
    assert rec["line_layer"] == "0"
    assert rec["line_color"] == "256"
