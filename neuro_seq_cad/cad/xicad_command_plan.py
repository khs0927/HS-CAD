from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.orchestrator.xicad_recipe_registry import get_xicad_recipe, is_scriptable_xicad_command
from src.orchestrator.xicad_safety_policy import decide_xicad_safety


SEMANTIC_TO_ALIAS = {
    "wall": "WAL",
    "door": "D1",
    "window": "W1",
    "column": "COL",
    "insulation": "INS",
    "stair": "STP",
    "parking": "PK",
    "room": "AE",
    "zone": "AE",
    "area": "AE",
}


def entity_to_xicad_command(entity: dict[str, Any]) -> dict[str, Any]:
    entity_type = str(entity.get("type") or entity.get("semantic_type") or "").lower()
    alias = SEMANTIC_TO_ALIAS.get(entity_type, "")
    if not alias:
        return {
            "entity_id": entity.get("id"),
            "semantic_type": entity_type,
            "recommended_alias": None,
            "mode": "fallback_dxf",
            "reason": "No XiCAD semantic mapping exists; keep DXFBuilder output.",
        }

    recipe = get_xicad_recipe(alias)
    function = recipe.function if recipe else ""
    notes = recipe.notes if recipe else ""
    decision = decide_xicad_safety(
        alias,
        function,
        notes,
        recipe_verified=bool(recipe and recipe.verified),
        recipe_scriptable=bool(recipe and recipe.scriptable),
    )
    return {
        "entity_id": entity.get("id"),
        "semantic_type": entity_type,
        "recommended_alias": alias,
        "function": function,
        "risk": decision.risk,
        "scriptable": is_scriptable_xicad_command(alias),
        "mode": "script_candidate" if decision.auto_run_allowed else "review_only",
        "reason": "; ".join(decision.reasons),
    }


def build_xicad_command_plan(entities: list[dict[str, Any]], *, source: str = "evidence_graph") -> dict[str, Any]:
    commands = [entity_to_xicad_command(entity) for entity in entities]
    return {
        "mode": "review_only" if not any(item.get("scriptable") for item in commands) else "script_candidate",
        "source": source,
        "fallback": "DXFBuilder remains canonical output",
        "commands": commands,
    }


def write_xicad_command_plan(entities: list[dict[str, Any]], out_dir: str | Path, *, source: str = "evidence_graph") -> dict[str, str]:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    plan = build_xicad_command_plan(entities, source=source)
    json_path = out / "xicad_command_plan.json"
    md_path = out / "xicad_script_report.md"
    json_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
    md_lines = [
        "# XiCAD Command Plan",
        "",
        f"- Mode: {plan['mode']}",
        f"- Source: {plan['source']}",
        f"- Fallback: {plan['fallback']}",
        "",
        "| Entity | Type | Alias | Function | Risk | Scriptable |",
        "|---|---|---|---|---|---|",
    ]
    for item in plan["commands"]:
        md_lines.append(
            f"| {item.get('entity_id', '')} | {item.get('semantic_type', '')} | "
            f"{item.get('recommended_alias', '') or ''} | {item.get('function', '') or ''} | "
            f"{item.get('risk', '') or ''} | {item.get('scriptable', False)} |"
        )
    md_path.write_text("\n".join(md_lines) + "\n", encoding="utf-8")
    return {"json": str(json_path), "markdown": str(md_path)}
