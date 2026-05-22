from __future__ import annotations

from dataclasses import asdict
from typing import Any

from .xicad_recipe_registry import get_xicad_recipe
from .xicad_safety_policy import decide_xicad_safety


def _command_to_dict(command: Any) -> dict[str, Any]:
    if hasattr(command, "to_dict"):
        return command.to_dict()
    if hasattr(command, "__dataclass_fields__"):
        return asdict(command)
    if isinstance(command, dict):
        return dict(command)
    return {
        "alias": str(command),
        "function": "",
        "description": "",
        "category": "UNKNOWN",
        "risk": "INTERACTIVE_PREVIEW",
    }


def find_xicad_candidates(query: str, category: str | None = None, limit: int = 12) -> list[dict[str, Any]]:
    """Return limited XiCAD candidates annotated with the stage-2 safety policy."""
    limit = max(1, min(int(limit or 12), 50))
    try:
        from src.orchestrator.xicad_taxonomy import search_xicad_commands

        rows = search_xicad_commands(query, category=category, limit=limit)
        candidates = [_command_to_dict(row) for row in rows]
    except Exception:
        candidates = _fallback_candidates(query, category=category)

    normalized: list[dict[str, Any]] = []
    for row in candidates[:limit]:
        alias = str(row.get("alias", "")).strip().upper()
        function = str(row.get("function", "")).strip()
        description = str(row.get("description", "")).strip()
        recipe = get_xicad_recipe(alias)
        decision = decide_xicad_safety(
            alias,
            function or (recipe.function if recipe else ""),
            description,
            recipe_verified=bool(recipe and recipe.verified),
            recipe_scriptable=bool(recipe and recipe.scriptable),
        )
        row["alias"] = alias
        row["function"] = function or (recipe.function if recipe else "")
        row["description"] = description
        row["category"] = row.get("category") or category or "UNKNOWN"
        row["risk"] = decision.risk
        row["auto_run_allowed"] = decision.auto_run_allowed
        row["safety_reasons"] = list(decision.reasons)
        row["recipe_verified"] = bool(recipe and recipe.verified)
        row["recipe_scriptable"] = bool(recipe and recipe.scriptable)
        normalized.append(row)
    return normalized


def _fallback_candidates(query: str, category: str | None = None) -> list[dict[str, Any]]:
    q = str(query or "").lower()
    base = [
        {"alias": "WAL", "function": "xiDrawWall", "description": "벽 그리기", "category": "DRAW_ARCH"},
        {"alias": "INS", "function": "xiInsul", "description": "단열재 그리기", "category": "DRAW_ARCH"},
        {"alias": "D1", "function": "xiDoor1", "description": "간단문 그리기", "category": "DRAW_ARCH"},
        {"alias": "W1", "function": "xiWin1", "description": "간단창 그리기", "category": "DRAW_ARCH"},
        {"alias": "AE", "function": "xiAE", "description": "면적 표시", "category": "AREA_QTY"},
        {"alias": "LC", "function": "xiChangeLayer", "description": "선택객체 켜 변경", "category": "LAYER_MANAGE"},
        {"alias": "BE", "function": "xiBE", "description": "H빔 C채널 L형강 그리기", "category": "DRAW_STRUCT"},
    ]
    tokens = [token for token in q.replace("/", " ").split() if token]
    out = []
    for row in base:
        if category and row["category"] != category:
            continue
        haystack = " ".join(str(v).lower() for v in row.values())
        if not tokens or any(token in haystack for token in tokens):
            out.append(row)
    return out or [row for row in base if not category or row["category"] == category]


def build_xicad_prompt_context(query: str, category: str | None = None, limit: int = 12) -> str:
    candidates = find_xicad_candidates(query, category=category, limit=limit)
    lines = [
        "[XiCAD Candidate Commands]",
        f"- query: {query}",
        f"- category: {category or 'AUTO'}",
        "",
    ]
    if not candidates:
        lines.append("- No XiCAD command candidates found. Use generic DXF output and ask for review.")
    for item in candidates:
        lines.append(
            f"- {item['alias']} / {item.get('function', '')} / "
            f"{item.get('description', '')} / category={item.get('category', 'UNKNOWN')} / "
            f"risk={item.get('risk', 'UNKNOWN')} / auto_run={item.get('auto_run_allowed', False)}"
        )
    lines += [
        "",
        "[Rules]",
        "- Do not invent XiCAD commands.",
        "- Use only listed aliases/functions.",
        "- Do not auto-run blocked or high-risk commands.",
        "- If no verified recipe exists, produce a command plan only.",
        "- DXFBuilder remains the canonical fallback output.",
    ]
    return "\n".join(lines) + "\n"
