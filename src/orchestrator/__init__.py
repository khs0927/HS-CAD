"""HS-CAD tool orchestration package.

This package keeps a central registry of every major HS-CAD tool family and
builds safe, priority-ordered workflows from a user task. The orchestrator is
planning-first: it does not mutate DWG files unless another existing command is
explicitly executed by the user.
"""

from .tool_registry import ToolCapability, ToolRegistry, build_default_registry
from .workflow_planner import WorkflowPlan, WorkflowStep, plan_hscad_workflow

__all__ = [
    "ToolCapability",
    "ToolRegistry",
    "WorkflowPlan",
    "WorkflowStep",
    "build_default_registry",
    "plan_hscad_workflow",
]
