from pathlib import Path

from src.integration.qa_pipeline import QAPipeline


def test_qa_pipeline_run_fileized(tmp_path):
    result = QAPipeline(tmp_path).run_fileized(
        Path("samples/reviewcontext_fileized_dxf_sample.json")
    )

    assert result.status == "ok"
    assert result.violation_count >= 1
    assert result.action_candidate_count >= 1
    assert result.command_plan_count >= 1

    assert Path(result.review_report_path).exists()
    assert Path(result.command_plan_report_path).exists()
    assert Path(result.qa_bundle_path).exists()
    assert Path(result.run_summary_path).exists()

    summary = Path(result.run_summary_path).read_text(encoding="utf-8")
    assert "HS-CAD QA Pipeline Summary" in summary
    assert "Dry-run only: true" in summary
