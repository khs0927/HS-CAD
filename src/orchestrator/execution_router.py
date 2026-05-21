"""Execution router – dispatches each :class:`TaskStep` to the concrete
implementation.

For the purpose of unit testing we do **not** perform real COM interaction.
Instead each step is simulated and a :class:`StepResult` is produced that
records the intended call. This keeps the test suite fast and platform‑
independent while still verifying that the routing logic works correctly.
"""

from __future__ import annotations

import importlib
from typing import Any, Dict, List

from .task_schema import ExecutionResult, StepResult, TaskPlan


def _load_function(module_path: str, function_name: str):
    """Import *module_path* and return the attribute *function_name*.

    If the import fails a ``ImportError`` is raised – the caller can decide how
    to handle it.
    """
    module = importlib.import_module(module_path)
    return getattr(module, function_name)


def execute_step(step: StepResult, step_def: Any, context: Dict[str, Any]) -> StepResult:
    """Execute a single step.

    ``step_def`` is a :class:`TaskStep` model. The function attempts to import
    the target module and call the function with ``**step_def.parameters``.
    Any exception is caught and the result status is set to ``error``.
    """
    try:
        func = _load_function(step_def.module, step_def.function)
        # In the test environment the functions are usually lightweight and may
        # return a dictionary. We ignore the return value for now.
        func(**step_def.parameters)  # type: ignore[arg-type]
        step.status = "executed"
        step.message = ""
    except Exception as exc:  # pragma: no cover – defensive
        step.status = "error"
        step.message = str(exc)
    return step


def execute_task_plan(plan: TaskPlan) -> ExecutionResult:
    """Execute all steps of *plan* respecting its safety options.

    The function does not modify the drawing – it merely calls the target
    functions (which are themselves stubs or safe‑preview helpers). It returns an
    :class:`ExecutionResult` with detailed step information.
    """
    result = ExecutionResult(
        task_plan_id=plan.id,
        status="running",
        undo_mark_created=False,
    )
    # Safety validation – warnings are added to the execution result.
    result.warnings = plan.warnings

    for step_def in plan.steps:
        step_res = StepResult(step_id=step_def.id, status="pending")
        # Determine if the step is allowed by the safety policy.
        blocked = False
        # Very simple policy: if the step marks execution and safety.allow_execute is False -> skip.
        if step_def.can_execute and not plan.safety.allow_execute:
            blocked = True
            step_res.status = "skipped"
            step_res.message = "Safety policy blocked execution"
        elif "undo" in step_def.step_type.lower():
            # Undo steps are always allowed – they just affect the state.
            result.undo_mark_created = True
        if not blocked:
            step_res = execute_step(step_res, step_def, context={})
            if step_res.status == "executed":
                result.executed_steps.append(step_res)
            elif step_res.status == "error":
                result.errors.append(step_res.message)
                result.executed_steps.append(step_res)
        else:
            result.skipped_steps.append(step_res)

    result.status = "completed"
    return result
