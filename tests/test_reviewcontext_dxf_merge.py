from pathlib import Path

from src.integration.reviewcontext_dxf_merge import (
    FileizedReviewAdapter,
    command_plan_from_review,
    review_fileized_record,
)


def test_fileized_adapter_builds_context():
    context = FileizedReviewAdapter.from_json(
        Path("samples/reviewcontext_fileized_dxf_sample.json")
    )

    assert context.drawing_id == "reviewcontext_sample_001"
    assert len(context.objects) >= 5
    assert len(context.texts) >= 2
    assert context.spatial is not None


def test_review_fileized_record_and_command_plan(tmp_path):
    review_out = tmp_path / "review_report.json"
    plan_out = tmp_path / "command_plan_report.json"

    review = review_fileized_record(
        Path("samples/reviewcontext_fileized_dxf_sample.json"),
        review_out,
    )

    assert review_out.exists()
    assert "summary" in review
    assert review["summary"]["violation_count"] >= 1
    assert any(
        v["code"] == "LAYER_SEMANTIC_MISMATCH" for v in review["violations"]
    )

    plan = command_plan_from_review(review_out, plan_out)

    assert plan_out.exists()
    assert "summary" in plan
    assert plan["summary"]["plan_count"] == review["summary"]["action_candidate_count"]
    assert all(item["dry_run"] is True for item in plan["command_plans"])
