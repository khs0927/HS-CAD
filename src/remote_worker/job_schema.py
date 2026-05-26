from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


AllowedAction = Literal[
    "inspect_only",
    "ensure_layer",
    "add_text_note",
    "add_leader_note",
    "normalize_layer_color",
]


class JobSource(BaseModel):
    type: Literal["local", "google_drive"] = "local"
    file_path: str | None = None
    file_id: str | None = None
    file_name: str | None = None
    allow_blank: bool = False


class JobAction(BaseModel):
    type: AllowedAction
    layer: str | None = None
    text: str | None = None
    position: tuple[float, float] | None = None
    leader_to: tuple[float, float] | None = None
    color: int | None = Field(default=None, ge=1, le=255)
    params: dict[str, Any] = Field(default_factory=dict)

    @field_validator("text")
    @classmethod
    def reject_empty_text(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("text must not be empty")
        return value


class RemoteDxfJob(BaseModel):
    job_id: str
    source: JobSource = Field(default_factory=JobSource)
    actions: list[JobAction] = Field(default_factory=list)
    outputs: list[Literal["dxf", "svg", "png", "change_report"]] = Field(
        default_factory=lambda: ["dxf", "svg", "change_report"]
    )
    output_dir: str = "outputs/jobs"

    @field_validator("job_id")
    @classmethod
    def safe_job_id(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("job_id is required")
        if any(ch in cleaned for ch in "\\/:*?\"<>|"):
            raise ValueError("job_id contains unsafe path characters")
        return cleaned

    def job_output_dir(self) -> Path:
        return Path(self.output_dir) / self.job_id
