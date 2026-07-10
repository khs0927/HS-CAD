from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator, model_validator


class JobStatus(str, Enum):
    pending = "pending"
    running = "running"
    cancelling = "cancelling"
    succeeded = "succeeded"
    failed = "failed"
    cancelled = "cancelled"
    blocked = "blocked"


class CommandStep(BaseModel):
    """One XiCAD command invocation.

    ``arguments`` contains the exact answers to XiCAD command-line prompts. Each
    item is sent on a new line after the alias. Interactive aliases are allowed
    in unattended mode only when this prompt contract is present.
    """

    alias: str = Field(..., min_length=1, max_length=32)
    arguments: list[str] = Field(default_factory=list)
    timeout_seconds: float = Field(default=120.0, ge=1.0, le=3600.0)
    allow_interactive: bool = False
    allow_high_risk: bool = False
    checkpoint: bool = True
    description: str = ""
    expected_min_entity_delta: int | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("alias")
    @classmethod
    def normalize_alias(cls, value: str) -> str:
        normalized = value.strip().upper()
        if not normalized or any(char in normalized for char in "\r\n;"):
            raise ValueError("alias contains unsafe characters")
        return normalized

    @field_validator("arguments")
    @classmethod
    def validate_arguments(cls, values: list[str]) -> list[str]:
        cleaned: list[str] = []
        for value in values:
            text = str(value)
            if "\x00" in text:
                raise ValueError("arguments may not contain NUL")
            cleaned.append(text.rstrip("\r\n"))
        return cleaned

    def command_text(self) -> str:
        return "\n".join([self.alias, *self.arguments]) + "\n"


class WorkflowSpec(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex)
    name: str = "XiCAD architectural workflow"
    source_dwg: Path
    working_dwg: Path
    xicad_root: Path
    steps: list[CommandStep] = Field(min_length=1)
    dry_run: bool = True
    approval_token: str | None = None
    save_after_each_step: bool = True
    keep_recovery_copy: bool = True
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_paths(self) -> "WorkflowSpec":
        source = self.source_dwg.expanduser()
        working = self.working_dwg.expanduser()
        if source == working:
            raise ValueError("working_dwg must be a separate copy, never the source DWG")
        self.source_dwg = source
        self.working_dwg = working
        self.xicad_root = self.xicad_root.expanduser()
        return self

    def approval_payload(self) -> dict[str, Any]:
        payload = self.model_dump(mode="json", exclude={"approval_token"})
        payload["dry_run"] = False
        return payload

    def expected_approval_token(self) -> str:
        canonical = json.dumps(self.approval_payload(), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:24]

    def is_approved(self) -> bool:
        return bool(self.approval_token) and self.approval_token == self.expected_approval_token()


class StepResult(BaseModel):
    index: int
    alias: str
    status: str
    started_at: str
    finished_at: str
    before_count: int | None = None
    after_count: int | None = None
    checkpoint_path: str | None = None
    error: str | None = None


class WorkflowResult(BaseModel):
    workflow_id: str
    status: JobStatus
    started_at: str
    finished_at: str
    working_dwg: str
    recovery_path: str | None = None
    steps: list[StepResult] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class JobRecord(BaseModel):
    id: str
    status: JobStatus
    workflow: WorkflowSpec
    created_at: str
    updated_at: str
    worker_id: str | None = None
    attempts: int = 0
    result: WorkflowResult | None = None
    error: str | None = None


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()
