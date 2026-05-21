"""XiCAD live plan utilities – thin wrappers around the existing safe‑bridge.

The functions expose a simple JSON‑serialisable representation that is
compatible with the orchestrator's expectations.
"""

from __future__ import annotations

from typing import Any, Dict

from src.extensions.xicad_safe_bridge.models import XicadSafeCommand, XicadSafety
from src.extensions.xicad_safe_bridge.planner import XicadSafePlanner
from src.extensions.xicad_safe_bridge.registry import default_xicad_registry


def _make_safe_command(alias: str, params: Dict[str, Any] | None = None) -> XicadSafeCommand:
    """Create a ``XicadSafeCommand`` for *alias*.

    The command is always a ``xicad_safe_plan`` with ``dry_run=True`` – the
    orchestrator can later decide to enable execution.
    """
    safety = XicadSafety()
    return XicadSafeCommand(
        command="xicad_safe_plan",
        alias=alias,
        load_first=False,
        dry_run=True,
        params=params or {},
        safety=safety,
    )


def create_xicad_safe_plan(alias: str, params: Dict[str, Any] | None = None) -> Dict[str, Any]:
    """Return a serialisable safe‑plan dictionary for *alias*.

    The function builds a ``XicadSafePlanner`` using the default registry and
    returns the ``model_dump`` of the created plan.
    """
    planner = XicadSafePlanner(default_xicad_registry())
    command = _make_safe_command(alias, params)
    plan = planner.build_plan(command)
    return plan.model_dump(mode="json")


def execute_xicad_plan_if_allowed(alias: str, allow_execute: bool = False, allow_interactive: bool = False, params: Dict[str, Any] | None = None) -> Dict[str, Any]:
    """Execute a XiCAD safe plan if ``allow_execute`` is ``True``.

    The function mirrors the CLI ``xicad-safe-run`` behaviour but returns the
    plan dictionary instead of printing it. When execution is not allowed the
    plan remains a dry‑run.
    """
    safety = XicadSafety(
        backup_required=True,
        preview_required=True,
        allow_interactive=allow_interactive,
        allow_high_risk=allow_execute,
    )
    command = XicadSafeCommand(
        command="xicad_safe_execute" if allow_execute else "xicad_safe_plan",
        alias=alias,
        load_first=False,
        dry_run=not allow_execute,
        params=params or {},
        safety=safety,
    )
    planner = XicadSafePlanner(default_xicad_registry())
    plan = planner.build_plan(command)
    return plan.model_dump(mode="json")
