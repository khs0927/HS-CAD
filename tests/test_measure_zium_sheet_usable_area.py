import json
import subprocess
import pathlib

def test_measure_zium_sheet_usable_area(tmp_path: pathlib.Path):
    out_dir = tmp_path / "zium_test"
    repo_root = pathlib.Path(__file__).resolve().parents[1]
    subprocess.check_call([
        "python",
        "tools/measure_zium_sheet_usable_area.py",
        "--out-dir",
        str(out_dir),
    ], cwd=str(repo_root))

    json_path = out_dir / "zium_sheet_usable_area.json"
    assert json_path.is_file()
    data = json.load(json_path.open(encoding="utf-8"))
    assert data["block_definition_exists"] is True
    assert data["needs_visual_check"] is False
    # Validate usable area bbox structure
    bbox = data["usable_drawing_area_bbox"]
    for key in ["xmin", "ymin", "xmax", "ymax"]:
        assert key in bbox
    # Ensure confidence is reasonable
    assert 0.0 <= data["confidence"] <= 1.0
