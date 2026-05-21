import json
from pathlib import Path

from src.merge_planner.builder import build_merge_candidate_plan


def test_build_merge_candidate_plan_plan_only(tmp_path: Path):
    session = tmp_path / "preview_session.json"
    styled = tmp_path / "styled_result.json"
    context = tmp_path / "style_context.json"
    session.write_text(json.dumps({"session_id": "s1"}), encoding="utf-8")
    context.write_text(json.dumps({"version": "test"}), encoding="utf-8")
    styled.write_text(
        json.dumps(
            {
                "entities": [
                    {
                        "original_entity": {"id": "w1", "entity_type": "wall", "confidence": 0.9},
                        "target_layer": "A-WALL",
                        "style_confidence": 0.9,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    plan = build_merge_candidate_plan(session, context, styled)
    assert plan.mode == "plan_only"
    assert plan.can_merge is False
    assert plan.requires_user_approval is True
    assert plan.merge_groups
    assert "purge" in plan.blocked_actions
