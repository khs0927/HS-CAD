from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from .xicad_safety_policy import decide_xicad_safety


@dataclass(frozen=True)
class XiCADRecipe:
    alias: str
    function: str
    category: str
    input_mode: str  # command_line | interactive | unknown
    verified: bool
    scriptable: bool
    notes: str

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        decision = decide_xicad_safety(
            self.alias,
            self.function,
            self.notes,
            recipe_verified=self.verified,
            recipe_scriptable=self.scriptable,
        )
        payload["risk"] = decision.risk
        payload["auto_run_allowed"] = decision.auto_run_allowed
        payload["safety_reasons"] = list(decision.reasons)
        return payload


# Important:
# Earlier drafts considered INS/AE/LC as scriptable. That is too risky until
# their command-line arguments are verified in a real ZWCAD + XiCAD session.
# Keep them review-only by default.
_RECIPES: dict[str, XiCADRecipe] = {
    "WAL": XiCADRecipe("WAL", "xiDrawWall", "DRAW_ARCH", "interactive", False, False, "Wall drawing command; keep review-only until argument contract is verified."),
    "D1": XiCADRecipe("D1", "xiDoor1", "DRAW_ARCH", "interactive", False, False, "Door command; likely interactive."),
    "W1": XiCADRecipe("W1", "xiWin1", "DRAW_ARCH", "interactive", False, False, "Window command; likely interactive."),
    "INS": XiCADRecipe("INS", "xiInsul", "DRAW_ARCH", "interactive", False, False, "Insulation command; useful but not verified for auto scripting."),
    "AE": XiCADRecipe("AE", "xiAE", "AREA_QTY", "interactive", False, False, "Area annotation command; keep review-only."),
    "LC": XiCADRecipe("LC", "xiChangeLayer", "LAYER_MANAGE", "interactive", False, False, "Layer change command mutates drawing; keep review-only."),
    "BE": XiCADRecipe("BE", "xiBE", "DRAW_STRUCT", "interactive", False, False, "Steel shape command; coordinate/argument contract not verified."),
}


def get_xicad_recipe(alias: str) -> XiCADRecipe | None:
    return _RECIPES.get(str(alias or "").strip().upper())


def is_scriptable_xicad_command(alias: str) -> bool:
    recipe = get_xicad_recipe(alias)
    if recipe is None:
        return False
    decision = decide_xicad_safety(
        recipe.alias,
        recipe.function,
        recipe.notes,
        recipe_verified=recipe.verified,
        recipe_scriptable=recipe.scriptable,
    )
    return decision.auto_run_allowed


def list_xicad_recipes() -> list[XiCADRecipe]:
    return sorted(_RECIPES.values(), key=lambda item: item.alias)


def recipe_summary() -> dict[str, Any]:
    rows = [recipe.to_dict() for recipe in list_xicad_recipes()]
    return {
        "recipe_count": len(rows),
        "auto_scriptable_count": sum(1 for row in rows if row["auto_run_allowed"]),
        "policy": "default_deny_until_verified",
        "recipes": rows,
    }
