from __future__ import annotations

from src.ai.planner import build_planner_prompt, plan_from_text_stub
from src.ai.prompts import SYSTEM_PROMPT_FOR_CAD_PLANNER, SYSTEM_PROMPT_FOR_XICAD_PLANNER


def test_cad_planner_prompt_enforces_json_only():
    assert "JSON" in SYSTEM_PROMPT_FOR_CAD_PLANNER
    assert "Never write Python" in SYSTEM_PROMPT_FOR_CAD_PLANNER
    assert "XiCAD aliases" in SYSTEM_PROMPT_FOR_CAD_PLANNER or "XiCAD" in SYSTEM_PROMPT_FOR_CAD_PLANNER


def test_xicad_planner_prompt_restricts_aliases():
    assert "provided alias catalog" in SYSTEM_PROMPT_FOR_XICAD_PLANNER
    assert "JSON" in SYSTEM_PROMPT_FOR_XICAD_PLANNER


def test_planner_stub_is_safe():
    result = plan_from_text_stub("벽을 이동해줘", {"layers": ["A-WALL"]})
    assert result["command"] == "unsupported_command"
    assert "LLM provider" in result["reason"]


def test_build_planner_prompt_contains_user_request():
    prompt = build_planner_prompt("A-WALL 이동", {"object_count": 10}, ["move_layer"])
    assert "A-WALL 이동" in prompt
    assert "move_layer" in prompt
