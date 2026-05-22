from __future__ import annotations

from src.orchestrator.agent_state import normalize_context
from src.orchestrator.intent_model import AgentIntent, classify_agent_intent
from src.orchestrator.intelligent_router import build_intelligent_route


def test_floorplan_task_routes_to_floorplan_process(tmp_path):
    result = build_intelligent_route("스캔 이미지 도면을 DXF로 만들어줘", has_image=True, out_dir=tmp_path)
    assert result.decision.primary_process == AgentIntent.FLOORPLAN_TO_CAD.value
    commands = [step["command"] for step in result.decision.selected_tools]
    assert any("floorplan" in command or "neuro_seq_cad" in command for command in commands)
    assert result.report_paths["json"]


def test_dwg_write_task_is_review_gated(tmp_path):
    result = build_intelligent_route("기존 DWG의 벽체와 문자를 수정해줘", has_dwg=True, wants_write=True, out_dir=tmp_path)
    assert result.decision.primary_process == AgentIntent.DWG_CHANGE_REVIEW_FIRST.value
    assert result.decision.held_tools


def test_xicad_arch_task_classification():
    context = normalize_context("벽체 두께를 유지하면서 단열재와 창문을 추가해줘")
    assert classify_agent_intent(context) == AgentIntent.XICAD_ARCH_DRAW


def test_steel_task_classification():
    context = normalize_context("H빔 보와 철골 기둥을 검토해줘")
    assert classify_agent_intent(context) == AgentIntent.HYBRID_STEEL_WORKFLOW


def test_missing_context_for_image_without_path(tmp_path):
    result = build_intelligent_route("이미지 도면을 CAD로 만들어줘", has_image=True, out_dir=tmp_path)
    assert any("Image" in item or "image" in item for item in result.decision.missing_context)
