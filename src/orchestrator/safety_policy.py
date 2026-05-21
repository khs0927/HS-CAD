"""Safety policy validation for a TaskPlan.

The policy checks the list of :class:`TaskStep` objects against the allowed
actions defined in :class:`SafetyOptions`. The implementation is deliberately
conservative – any step that is potentially unsafe and not explicitly
allowed generates a warning.
"""

from __future__ import annotations

from typing import List

from .task_schema import SafetyOptions, TaskPlan, TaskStep

# ---------------------------------------------------------------------------
# Helper checks – each returns a warning string when the condition is violated.
# ---------------------------------------------------------------------------

def _check_save_operations(step: TaskStep, safety: SafetyOptions) -> str | None:
    if step.step_type.lower().startswith("save") and not safety.allow_save:
        return f"Save operation blocked in step {step.id}"
    return None


def _check_purge_delete_explode(step: TaskStep, safety: SafetyOptions) -> str | None:
    forbidden = {"purge", "delete", "explode"}
    if any(word in step.step_type.lower() for word in forbidden) and not (
        safety.allow_purge and safety.allow_delete and safety.allow_explode
    ):
        return f"Forbidden destructive command in step {step.id}: {step.step_type}"
    return None


def _check_block_definition_edit(step: TaskStep, safety: SafetyOptions) -> str | None:
    if "block" in step.step_type.lower() and "edit" in step.step_type.lower() and not safety.allow_block_definition_edit:
        return f"Block definition edit blocked in step {step.id}"
    return None


def _check_raw_command(step: TaskStep, safety: SafetyOptions) -> str | None:
    if step.step_type.lower() == "raw_command" and not safety.allow_execute:
        return f"Raw command execution blocked in step {step.id}"
    return None


def _check_layer_zero(step: TaskStep, safety: SafetyOptions) -> str | None:
    if "layer 0" in step.description.lower() and not safety.allow_layer_zero:
        return f"Layer 0 modification blocked in step {step.id}"
    return None


def _check_interactive_xicad(step: TaskStep, safety: SafetyOptions) -> str | None:
    if step.step_type == "xicad_execute_preview" and not safety.allow_interactive:
        return f"Interactive XiCAD command blocked in step {step.id}"
    return None


def _check_execute_without_allow(step: TaskStep, safety: SafetyOptions) -> str | None:
    if step.can_execute and not safety.allow_execute:
        return f"Execution blocked (allow_execute=False) in step {step.id}"
    return None


def validate_task_plan_safety(plan: TaskPlan) -> List[str]:
    """Validate *plan* against its :class:`SafetyOptions`.

    The function iterates over all steps, runs a series of concrete checks and
    returns a list of warning messages. An empty list means the plan is
    considered safe.
    """
    warnings: List[str] = []
    safety = plan.safety
    for step in plan.steps:
        # Order matters – we want the most specific warnings first.
        for check in (
            _check_save_operations,
            _check_purge_delete_explode,
            _check_block_definition_edit,
            _check_raw_command,
            _check_layer_zero,
            _check_interactive_xicad,
            _check_execute_without_allow,
        ):
            warning = check(step, safety)
            if warning:
                warnings.append(warning)
    return warnings
