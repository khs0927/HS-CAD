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

    def validate_preconditions(self, params: dict[str, Any], scan_state: dict[str, Any] | None = None) -> list[str]:
        """Validate recipe-specific preconditions and parameter contracts (Stage-2 Upgrade)."""
        errors: list[str] = []
        alias_u = self.alias.upper()
        
        # 1. Common validation (requires params dict)
        if not isinstance(params, dict):
            errors.append("Parameters must be a key-value dictionary.")
            return errors

        # 2. Specific Command Preset Validation Rules
        if alias_u == "WAL":
            # WAL Rule: Wall thickness, height or base line references
            if "thickness" not in params and "width" not in params:
                errors.append("WAL requires either 'thickness' or 'width' parameter.")
            if scan_state:
                # Check for baseline layer presence or A-WALL layer health
                layers = scan_state.get("layers", {})
                if not any(k for k in layers if "WALL" in str(k).upper() or "벽체" in str(k)):
                    errors.append("Recommendation: No existing wall layer (e.g. A-WALL, wall1) detected in current drawing scan.")

        elif alias_u == "COL":
            # COL Rule: Coordinates check for column placements
            if "points" not in params and "coordinates" not in params and "insertion_point" not in params:
                errors.append("COL requires placement coordinates (e.g., 'points', 'coordinates', or 'insertion_point').")
            points = params.get("points") or params.get("coordinates") or params.get("insertion_point")
            if points and not isinstance(points, list):
                errors.append("Placement points must be specified as a list of coordinates.")

        elif alias_u == "D1" or alias_u == "W1":
            # Door & Window Rules: Requires sizing specs and reference wall handle
            if "width" not in params and "size" not in params:
                errors.append(f"{alias_u} command requires a size or width parameter.")
            if "wall_handle" not in params and "target_wall" not in params:
                errors.append(f"{alias_u} requires reference target wall ('wall_handle' or 'target_wall') for integration.")

        elif alias_u == "INS":
            # INS Rule: Insulation thickness and target object
            if "thickness" not in params and "depth" not in params:
                errors.append("INS requires insulation 'thickness' or 'depth'.")

        elif alias_u == "BE":
            # BE Rule: Steel structure standard shapes
            if "section" not in params and "profile" not in params:
                errors.append("BE requires structural steel profile specifications (e.g., 'section' or 'profile').")

        elif alias_u == "LC":
            # LC Rule: Layer change parameters
            if "target_layer" not in params and "to_layer" not in params:
                errors.append("LC requires 'target_layer' or 'to_layer' parameter.")

        return errors


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

