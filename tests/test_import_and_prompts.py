from __future__ import annotations

from src.ai.prompts import SAFETY_RULES_DESCRIPTION, SYSTEM_PROMPT_FOR_CAD_PLANNER, SYSTEM_PROMPT_FOR_XICAD_PLANNER


def test_com_adapter_import_is_safe_without_connecting() -> None:
    from src.adapters.zwcad_com_adapter import ZWCADCOMAdapter

    adapter = ZWCADCOMAdapter()
    assert adapter.app is None


def test_ai_planner_prompt_requires_json_only_and_no_python() -> None:
    prompt = SYSTEM_PROMPT_FOR_CAD_PLANNER.lower()
    assert "json" in prompt
    assert "never generate or execute python code" in prompt
    assert "safe catalog" in SYSTEM_PROMPT_FOR_XICAD_PLANNER.lower()
    assert "backup_required=true" in SAFETY_RULES_DESCRIPTION
    assert "aliases present in the supplied safe catalog" in SYSTEM_PROMPT_FOR_XICAD_PLANNER
