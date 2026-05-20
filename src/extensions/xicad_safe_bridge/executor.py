from __future__ import annotations

from typing import Protocol

from .models import XicadExecutionPlan, XicadSafeCommand
from .planner import XicadSafePlanner


class SupportsZwcadCommand(Protocol):
    """Minimal adapter protocol required by the safe executor."""

    def run_command(self, command_text: str) -> None:
        ...


class XicadSafeExecutor:
    """Executes a safe XiCAD plan through a ZWCAD-like adapter.

    The executor intentionally does not know about ZWCAD COM details.
    This avoids conflicts with ongoing Codex work in zwcad_com_adapter.py.
    """

    def __init__(self, planner: XicadSafePlanner) -> None:
        self.planner = planner

    def preview(self, command: XicadSafeCommand) -> XicadExecutionPlan:
        return self.planner.build_plan(command)

    def execute(self, command: XicadSafeCommand, adapter: SupportsZwcadCommand) -> XicadExecutionPlan:
        plan = self.planner.build_plan(command)
        if not plan.can_execute:
            return plan

        for command_text in plan.commands_to_send:
            if command_text.startswith(";"):
                continue
            adapter.run_command(command_text)
        return plan
