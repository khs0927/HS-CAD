from __future__ import annotations

from .models import XicadExecutionPlan, XicadRisk, XicadSafeCommand
from .registry import XicadAliasRegistry


class XicadSafePlanner:
    """Builds safe preview plans for XiCAD command execution."""

    def __init__(self, registry: XicadAliasRegistry) -> None:
        self.registry = registry

    def build_plan(self, command: XicadSafeCommand) -> XicadExecutionPlan:
        alias = self.registry.require(command.alias)
        warnings: list[str] = []
        steps: list[str] = []

        steps.append(f"Validate XiCAD alias: {alias.alias} ({alias.name or alias.category.value})")

        if command.load_first:
            steps.append("Load XiCAD bootstrap before running the command.")

        steps.append(f"Send XiCAD alias to ZWCAD command line: {alias.alias}")

        can_execute = True

        if alias.interactive_required and not command.safety.allow_interactive:
            can_execute = False
            warnings.append(
                "This XiCAD command appears to require interactive input. "
                "Set safety.allow_interactive=true only after confirming the workflow."
            )

        if alias.risk == XicadRisk.high and not command.safety.allow_high_risk:
            can_execute = False
            warnings.append("High-risk XiCAD command blocked. Set allow_high_risk=true only for trusted operations.")

        if command.dry_run:
            can_execute = False
            warnings.append("Dry-run mode is enabled. No command will be sent to ZWCAD.")

        if command.safety.backup_required:
            steps.insert(0, "Create or verify DWG backup before execution.")

        if command.safety.preview_required:
            steps.insert(0, "Show execution preview to the user.")

        commands_to_send: list[str] = []
        if command.load_first:
            commands_to_send.append("; XiCAD bootstrap should be loaded before this command")
        commands_to_send.append(alias.alias)

        return XicadExecutionPlan(
            alias=alias.alias,
            alias_name=alias.name,
            category=alias.category,
            risk=alias.risk,
            interactive_required=alias.interactive_required,
            can_execute=can_execute,
            dry_run=command.dry_run,
            load_first=command.load_first,
            commands_to_send=commands_to_send,
            steps=steps,
            warnings=warnings,
            metadata={"params": command.params},
        )
