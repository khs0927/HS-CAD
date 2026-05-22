from __future__ import annotations

from src.orchestrator.xicad_recipe_registry import is_scriptable_xicad_command, recipe_summary
from src.orchestrator.xicad_safety_policy import BLOCKED, HIGH_RISK, classify_xicad_risk, decide_xicad_safety


def test_dangerous_aliases_are_blocked_or_high_risk():
    assert classify_xicad_risk("ABX", "xiAllBlockExplode", "내부 모든 블럭 폭파") == BLOCKED
    assert classify_xicad_risk("ELY", "", "선택켜 객체 모두 삭제") == BLOCKED
    assert classify_xicad_risk("PPP", "", "다중출력") in {HIGH_RISK, BLOCKED}


def test_korean_risk_keywords_are_classified():
    assert classify_xicad_risk("TMP", "", "선택 객체 삭제") == BLOCKED
    assert classify_xicad_risk("TMP", "", "블록 폭파") == BLOCKED
    assert classify_xicad_risk("TMP", "", "저장없이 닫기") == BLOCKED
    assert classify_xicad_risk("TMP", "", "일괄 출력") == HIGH_RISK


def test_unverified_recipes_are_not_scriptable():
    assert is_scriptable_xicad_command("INS") is False
    assert is_scriptable_xicad_command("AE") is False
    assert is_scriptable_xicad_command("LC") is False


def test_safety_decision_requires_verified_scriptable_recipe():
    decision = decide_xicad_safety("INS", "xiInsul", "단열재 그리기", recipe_verified=False, recipe_scriptable=True)
    assert decision.auto_run_allowed is False
    assert "No verified recipe exists." in decision.reasons


def test_recipe_summary_is_default_deny():
    summary = recipe_summary()
    assert summary["policy"] == "default_deny_until_verified"
    assert summary["auto_scriptable_count"] == 0
