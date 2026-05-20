"""Safe bridge layer for XiCAD integration.

This package is intentionally isolated from the main XiCAD adapter to avoid
merge conflicts while Codex or another coding agent is working on core files.
"""

from .models import XicadAlias, XicadSafeCommand, XicadExecutionPlan
from .registry import XicadAliasRegistry, default_xicad_registry
from .planner import XicadSafePlanner
from .executor import XicadSafeExecutor

__all__ = [
    "XicadAlias",
    "XicadSafeCommand",
    "XicadExecutionPlan",
    "XicadAliasRegistry",
    "default_xicad_registry",
    "XicadSafePlanner",
    "XicadSafeExecutor",
]
