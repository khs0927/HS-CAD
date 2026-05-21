from __future__ import annotations
PROMPT_SYSTEM = """You convert Korean/English natural-language CAD edit requests into the allowed JSON command schema only. Never output Python code."""


def plan_from_text_stub(request: str, context: dict | None = None) -> dict:
    return {
        "command": "unsupported_command",
        "reason": "LLM provider is not configured; safe stub did not plan a mutation.",
        "request": request,
        "context": context or {},
    }


def build_planner_prompt(request: str, context: dict | None = None, allowed_commands: list[str] | None = None) -> str:
    commands = ", ".join(allowed_commands or [])
    return (
        f"{PROMPT_SYSTEM}\n"
        f"Allowed commands: {commands}\n"
        f"Context: {context or {}}\n"
        f"User request: {request}\n"
        "Return JSON only."
    )
