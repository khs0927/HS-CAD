"""Task planner – converts a :class:`TaskIntent` into an executable :class:`TaskPlan`.

The implementation is intentionally straightforward: each supported
``intent_type`` maps to a small list of :class:`TaskStep` objects that invoke the
corresponding functions from the ``integrations.zwcad_live`` or other modules.
Only the step definitions required by the tests are provided.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import List

from .task_schema import TaskIntent, TaskPlan, TaskStep, SafetyOptions

# ---------------------------------------------------------------------------
# Simple factory helpers for creating steps
# ---------------------------------------------------------------------------

def _make_step(step_type: str, description: str, module: str, function: str, parameters: dict | None = None, can_execute: bool = False, dry_run: bool = True) -> TaskStep:
    return TaskStep(
        step_type=step_type,
        description=description,
        module=module,
        function=function,
        parameters=parameters or {},
        can_execute=can_execute,
        dry_run=dry_run,
        expected_outputs=[],
    )

# ---------------------------------------------------------------------------
# Planner functions – each returns a list[TaskStep]
# ---------------------------------------------------------------------------

def plan_analyze_active_drawing(intent: TaskIntent) -> List[TaskStep]:
    return [_make_step(
        step_type="active_probe",
        description="Collect active document information and statistics",
        module="integrations.zwcad_live.active_document_probe",
        function="write_active_probe_json",
        parameters={"out_path": "generated/live_probe/active_probe.json"},
        can_execute=False,
        dry_run=True,
    )]


def plan_analyze_zero_layer(intent: TaskIntent) -> List[TaskStep]:
    # Reuse the same active probe – the zero‑layer analysis is performed downstream.
    return plan_analyze_active_drawing(intent)


def plan_dynamic_block_report(intent: TaskIntent) -> List[TaskStep]:
    return [_make_step(
        step_type="dynamic_block_report",
        description="Generate a report of dynamic block usage grouped by EffectiveName",
        module="integrations.zwcad_live.dynamic_block_report",
        function="write_dynamic_block_report_json",
        parameters={"out_path": "generated/reports/dynamic_block_report.json"},
        can_execute=False,
        dry_run=True,
    )]


def plan_remap_layers_preview(intent: TaskIntent) -> List[TaskStep]:
    # The preview workflow lives in ``image_to_cad.auto`` – we call the same helper.
    return [_make_step(
        step_type="layer_remap_preview",
        description="Run live preview for layer remapping without saving",
        module="image_to_cad.auto.live_preview",
        function="apply_live_preview",
        parameters={"min_confidence": 0.82, "allow_layer_zero": False},
        can_execute=False,
        dry_run=True,
    )]


def plan_xicad_safe_plan(intent: TaskIntent) -> List[TaskStep]:
    return [_make_step(
        step_type="xicad_safe_plan",
        description="Create a XiCAD safe execution plan (dry‑run)",
        module="integrations.zwcad_live.xicad_live_plan",
        function="create_xicad_safe_plan",
        parameters={"alias": intent.parameters.get("xicad_alias", "")},
        can_execute=False,
        dry_run=True,
    )]


def plan_xicad_execute_preview(intent: TaskIntent) -> List[TaskStep]:
    return [_make_step(
        step_type="xicad_live_execute",
        description="Execute a XiCAD command preview (dry‑run)",
        module="integrations.zwcad_live.xicad_live_plan",
        function="execute_xicad_plan_if_allowed",
        parameters={"alias": intent.parameters.get("xicad_alias", ""), "allow_execute": False, "allow_interactive": False},
        can_execute=False,
        dry_run=True,
    )]


def plan_lisp_preview_load(intent: TaskIntent) -> List[TaskStep]:
    return [_make_step(
        step_type="lisp_preview_load",
        description="Validate LISP file path and show load command",
        module="integrations.zwcad_live.lisp_live_loader",
        function="preview_lisp_load",
        parameters={"path": intent.parameters.get("file_path", "")},
        can_execute=False,
        dry_run=True,
    )]


def plan_lisp_live_load(intent: TaskIntent) -> List[TaskStep]:
    return [_make_step(
        step_type="lisp_live_load",
        description="Load LISP file into ZWCAD (preview only unless allowed)",
        module="integrations.zwcad_live.lisp_live_loader",
        function="send_lisp_load_if_allowed",
        parameters={"path": intent.parameters.get("file_path", ""), "allow_execute": False},
        can_execute=False,
        dry_run=True,
    )]


def plan_insert_image_result(intent: TaskIntent) -> List[TaskStep]:
    return [_make_step(
        step_type="image_insert_preview",
        description="Insert image result DXF as a block preview without saving",
        module="integrations.zwcad_live.image_insert_workflow",
        function="preview_image_insert",
        parameters={
            "dxf_path": intent.parameters.get("file_path", ""),
            "base_point": intent.parameters.get("base_point", []),
            "scale": intent.parameters.get("scale"),
            "rotation": intent.parameters.get("rotation"),
        },
        can_execute=False,
        dry_run=True,
    )]


def plan_undo_preview(intent: TaskIntent) -> List[TaskStep]:
    return [_make_step(
        step_type="undo_preview",
        description="Execute UNDO BACK to revert the last preview",
        module="integrations.zwcad_live.undo_guard",
        function="undo_back_to_mark",
        parameters={},
        can_execute=False,
        dry_run=True,
    )]

# ---------------------------------------------------------------------------
# Mapping from intent_type to planner function
# ---------------------------------------------------------------------------
_INTENT_PLANNERS = {
    "analyze_active_drawing": plan_analyze_active_drawing,
    "analyze_zero_layer": plan_analyze_zero_layer,
    "dynamic_block_report": plan_dynamic_block_report,
    "remap_layers_preview": plan_remap_layers_preview,
    "xicad_safe_plan": plan_xicad_safe_plan,
    "xicad_execute_preview": plan_xicad_execute_preview,
    "lisp_preview_load": plan_lisp_preview_load,
    "lisp_live_load": plan_lisp_live_load,
    "insert_image_result": plan_insert_image_result,
    "undo_preview": plan_undo_preview,
}


def build_task_plan(intent: TaskIntent) -> TaskPlan:
    """Create a :class:`TaskPlan` from *intent*.

    The function looks up a planner based on ``intent.intent_type``. If the
    intent is unknown an empty plan is returned (with a warning).
    """
    steps: List[TaskStep] = []
    warnings = []
    planner = _INTENT_PLANNERS.get(intent.intent_type)
    if planner:
        steps = planner(intent)
    else:
        warnings.append(f"Unsupported intent type: {intent.intent_type}")
    # Determine if the plan can execute – preview‑only plans are safe.
    can_execute = any(step.can_execute for step in steps)
    # Build the TaskPlan model.
    plan = TaskPlan(
        raw_user_command=intent.raw_user_command,
        intent=intent,
        steps=steps,
        safety=SafetyOptions(),
        dry_run=True,
        preview_mode=True,
        can_execute=can_execute,
        warnings=warnings,
    )
    return plan
