"""Task, Intent, and Result schemas for CAD task orchestrator.

This module defines pydantic models that describe:
- The parsed user intent (TaskIntent)
- The execution plan derived from the intent (TaskPlan and TaskStep)
- Safety options controlling allowed actions (SafetyOptions)
- The final execution result (ExecutionResult and StepResult)

Only the fields required by the orchestrator tests are included. Additional fields can be added later.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, validator


class SafetyOptions(BaseModel):
    """Options that control which potentially unsafe actions are permitted.

    All options default to ``False`` except ``create_undo_mark`` and ``preview_only``
    which are ``True`` because the orchestration workflow works in a preview mode
    and always creates an UNDO MARK before mutating the drawing.
    """

    allow_execute: bool = False
    allow_interactive: bool = False
    allow_layer_zero: bool = False
    allow_save: bool = False
    allow_save_as: bool = False
    allow_purge: bool = False
    allow_delete: bool = False
    allow_explode: bool = False
    allow_block_definition_edit: bool = False
    create_undo_mark: bool = True
    preview_only: bool = True


class TaskIntent(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    raw_user_command: str
    intent_type: str
    target: Optional[str] = None
    action: str
    parameters: Dict[str, Any] = Field(default_factory=dict)
    confidence: float = 1.0
    requires_zwcad: bool = False
    requires_xicad: bool = False
    requires_lisp: bool = False
    requires_image_result: bool = False
    risk_level: str = "low"
    reason: str = ""

    @validator("intent_type")
    def _non_empty_intent(cls, v: str) -> str:
        if not v:
            raise ValueError("intent_type cannot be empty")
        return v

    @validator("action")
    def _non_empty_action(cls, v: str) -> str:
        if not v:
            raise ValueError("action cannot be empty")
        return v


class TaskStep(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    step_type: str
    description: str
    module: str
    function: str
    parameters: Dict[str, Any] = Field(default_factory=dict)
    can_execute: bool = False
    dry_run: bool = True
    risk_level: str = "low"
    expected_outputs: List[str] = Field(default_factory=list)


class TaskPlan(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat(timespec="seconds"))
    raw_user_command: str
    intent: TaskIntent
    steps: List[TaskStep] = Field(default_factory=list)
    safety: SafetyOptions = Field(default_factory=SafetyOptions)
    dry_run: bool = True
    preview_mode: bool = True
    can_execute: bool = False
    warnings: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class StepResult(BaseModel):
    step_id: str
    status: str  # e.g., "executed", "skipped", "error"
    message: str = ""
    output_files: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ExecutionResult(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    task_plan_id: str
    started_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat(timespec="seconds"))
    finished_at: Optional[str] = None
    status: str = "pending"  # "running", "completed", "failed"
    executed_steps: List[StepResult] = Field(default_factory=list)
    skipped_steps: List[StepResult] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    errors: List[str] = Field(default_factory=list)
    output_files: List[str] = Field(default_factory=list)
    undo_mark_created: bool = False
    saved: bool = False
