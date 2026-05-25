from __future__ import annotations
import sys
from pathlib import Path

# Add src to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

def test_floorplan_pipeline_dry_run(tmp_path):
    """Test the complete Floorplan-to-CAD pipeline in Dry-Run mode and check that it outputs all standard files."""
    from neuro_seq_cad.app.cli import analyze
    
    # Target image path (will fail to load and automatically fall back to synthetic floorplan generation)
    dummy_image = tmp_path / "test_plan.png"
    
    # Run E2E pipeline with dry_run=True, vlm_refine=True
    analyze(image=dummy_image, output_dir=tmp_path, dry_run=True, vlm_refine=True)
    
    # Verify all expected outputs are generated in the temporary directory
    expected_files = [
        "synthetic_floorplan.png",
        "synthetic_floorplan_normalized.png",
        "synthetic_floorplan.dxf",
        "synthetic_floorplan_overlay_qa.png",
        "synthetic_floorplan_qa_report.md",
        "synthetic_floorplan_qa_report.html",
    ]
    
    for filename in expected_files:
        filepath = tmp_path / filename
        assert filepath.exists(), f"Expected file {filename} was not created."
        assert filepath.stat().st_size > 0, f"File {filename} is empty."
