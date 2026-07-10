from __future__ import annotations

from pathlib import Path
from typing import Any

from src.extensions.xicad_safe_bridge.models import XicadRisk
from src.extensions.xicad_safe_bridge.registry import XicadAliasRegistry, default_xicad_registry
from src.orchestrator.xicad_recipe_registry import get_xicad_recipe

from .models import CommandStep


class AutomationCatalog:
    """Expose every discovered XiCAD alias with explicit unattended capability."""

    def __init__(self, registry: XicadAliasRegistry) -> None:
        self.registry = registry

    @classmethod
    def from_xicad_root(cls, xicad_root: str | Path | None) -> "AutomationCatalog":
        if not xicad_root:
            return cls(default_xicad_registry())
        key_path = Path(xicad_root) / "Lisp" / "xiShortkey_origin.key"
        return cls(XicadAliasRegistry.from_key_file(key_path))

    def describe(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for item in self.registry.list():
            recipe = get_xicad_recipe(item.alias)
            rows.append(
                {
                    "alias": item.alias,
                    "name": item.name,
                    "description": item.description,
                    "category": item.category.value,
                    "risk": item.risk.value,
                    "interactive_required": item.interactive_required,
                    "verified_recipe": bool(recipe and recipe.verified),
                    "scriptable_recipe": bool(recipe and recipe.scriptable),
                    "unattended_ready": bool(recipe and recipe.verified and recipe.scriptable),
                    "source": item.raw.get("source", "built-in"),
                }
            )
        return rows

    def validate_step(self, step: CommandStep) -> list[str]:
        alias = self.registry.require(step.alias)
        problems: list[str] = []
        recipe = get_xicad_recipe(step.alias)

        if alias.risk == XicadRisk.high and not step.allow_high_risk:
            problems.append(f"{step.alias}: high-risk command requires allow_high_risk=true")

        if alias.interactive_required:
            has_contract = bool(step.arguments) or bool(recipe and recipe.verified and recipe.scriptable)
            if not step.allow_interactive:
                problems.append(f"{step.alias}: interactive command requires allow_interactive=true")
            elif not has_contract:
                problems.append(
                    f"{step.alias}: no verified prompt contract. Record arguments with "
                    "xicad-contract-wizard or provide exact arguments in the workflow."
                )
        return problems

    def validate_steps(self, steps: list[CommandStep]) -> list[str]:
        problems: list[str] = []
        for step in steps:
            try:
                problems.extend(self.validate_step(step))
            except ValueError as exc:
                problems.append(str(exc))
        return problems
