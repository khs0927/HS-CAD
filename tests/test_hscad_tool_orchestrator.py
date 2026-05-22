from __future__ import annotations

from src.orchestrator.tool_registry import build_default_registry
from src.orchestrator.workflow_planner import infer_intent, plan_hscad_workflow


def test_registry_contains_major_tool_families():
    registry = build_default_registry()
    families = registry.families()
    assert "inspection" in families
    assert "floorplan" in families
    assert "standards" in families
    assert "mutation-preview" in families
    assert "mutation-execute" in families


def test_floorplan_image_task_prefers_floorplan_pipeline():
    plan = plan_hscad_workflow("스캔 이미지 도면을 dxf로 만들어줘", has_image=True)
    commands = [step.command for step in plan.steps]
    assert plan.selected_intent == "floorplan_to_cad"
    assert "floorplan-analyze" in commands
    assert any("neuro_seq_cad" in command for command in commands)
    assert all(not step.needs_review for step in plan.steps)


def test_dwg_change_is_review_gated():
    plan = plan_hscad_workflow("기존 dwg의 벽체와 문자를 수정해줘", has_dwg=True, wants_write=True)
    assert plan.selected_intent == "dwg_change_review_first"
    assert any(step.command == "run-command --dry-run" for step in plan.steps)
    assert any(step.needs_review for step in plan.steps)
    assert plan.mode == "review-gated"


def test_xicad_task_uses_safe_bridge_first():
    plan = plan_hscad_workflow("XiCAD 벽체 명령을 사용해서 단열 벽체 계획을 짜줘")
    commands = [step.command for step in plan.steps]
    assert plan.selected_intent == "xicad_safe_workflow"
    assert "xicad-safe-catalog" in commands
    assert "xicad-safe-plan" in commands


def test_intent_inference_for_hybrid_steel():
    assert infer_intent("H빔 보와 철골 기둥을 검토해줘") == "hybrid_steel_workflow"
