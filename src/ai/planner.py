from __future__ import annotations

from typing import Any

from src.ai.prompts import SYSTEM_PROMPT_FOR_CAD_PLANNER, USER_PROMPT_TEMPLATE


def build_planner_prompt(user_request: str, drawing_context: dict[str, Any] | None = None, available_commands: list[str] | None = None) -> str:
    return SYSTEM_PROMPT_FOR_CAD_PLANNER + "\n\n" + USER_PROMPT_TEMPLATE.format(
        user_request=user_request,
        drawing_context=drawing_context or {},
        available_commands=available_commands or [],
    )


def plan_from_text_stub(text: str, context: dict[str, Any] | None = None) -> dict[str, Any]:
    """Placeholder for a future LLM provider.

    This function intentionally does not call a model. It returns a safe
    unsupported-command envelope so CLI/UI code can be developed without giving
    an LLM execution authority.
    """
    return {
        "command": "unsupported_command",
        "reason": "LLM provider is not connected yet. Use validated JSON command files for now.",
        "user_request": text,
        "context_keys": sorted((context or {}).keys()),
    }
