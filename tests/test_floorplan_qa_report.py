from __future__ import annotations
import sys
from pathlib import Path
import pytest

# Add src to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

def test_floorplan_qa_reports(tmp_path):
    """Test generating QA reports (Markdown and HTML) and verify they contain mandatory metrics and summaries."""
    from neuro_seq_cad.app.cli import analyze
    
    # Run E2E pipeline to generate reports
    dummy_image = tmp_path / "test_plan.png"
    analyze(image=dummy_image, output_dir=tmp_path, dry_run=True, vlm_refine=True)
    
    md_report_path = tmp_path / "synthetic_floorplan_qa_report.md"
    html_report_path = tmp_path / "synthetic_floorplan_qa_report.html"
    
    assert md_report_path.exists()
    assert html_report_path.exists()
    
    # Verify markdown contents
    md_content = md_report_path.read_text(encoding="utf-8")
    assert "품질 보증" in md_content
    assert "VLM" in md_content
    assert "Bath" in md_content or "Bathroom" in md_content
    assert "스케일" in md_content
    assert "종합 평균 신뢰도" in md_content
    
    # Verify HTML contents
    html_content = html_report_path.read_text(encoding="utf-8")
    assert "<html" in html_content.lower()
    assert "Outfit" in html_content or "Noto Sans" in html_content
    assert "Bathroom" in html_content
    assert "Wall" in html_content or "Door" in html_content
