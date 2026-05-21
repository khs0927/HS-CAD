from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field


FileizerStatus = Literal["success", "partial", "failed", "unavailable"]


class FileizedEntity(BaseModel):
    """A normalized raw entity extracted from a drawing/document file."""

    entity_id: str = ""
    entity_type: str = "UNKNOWN"
    layer: str | None = None
    block_name: str | None = None
    text: str | None = None
    geometry: dict[str, Any] = Field(default_factory=dict)
    style: dict[str, Any] = Field(default_factory=dict)
    bbox: list[float] = Field(default_factory=list)
    source: str = ""
    confidence: float = 1.0


class FileizedText(BaseModel):
    text: str
    normalized_text: str = ""
    page: int | None = None
    layer: str | None = None
    bbox: list[float] = Field(default_factory=list)
    source: str = ""
    confidence: float = 1.0


class FileizedDimension(BaseModel):
    raw_text: str = ""
    measurement: str | None = None
    layer: str | None = None
    geometry: dict[str, Any] = Field(default_factory=dict)
    source: str = ""
    confidence: float = 1.0


class FileizedDrawingRecord(BaseModel):
    """The intermediate fileized representation.

    This is intentionally *not* converted into company style. Company style is
    applied later by company_profile/canonical_to_company_mapper.py.
    """

    file_id: str
    source_path: str
    relative_path: str = ""
    extension: str = ""
    fileizer: str
    fileizer_version: str = ""
    status: FileizerStatus = "success"
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")
    metadata: dict[str, Any] = Field(default_factory=dict)
    layers: list[dict[str, Any]] = Field(default_factory=list)
    blocks: list[dict[str, Any]] = Field(default_factory=list)
    entities: list[FileizedEntity] = Field(default_factory=list)
    texts: list[FileizedText] = Field(default_factory=list)
    dimensions: list[FileizedDimension] = Field(default_factory=list)
    tables: list[dict[str, Any]] = Field(default_factory=list)
    hatches: list[dict[str, Any]] = Field(default_factory=list)
    layouts: list[dict[str, Any]] = Field(default_factory=list)
    geometry_summary: dict[str, Any] = Field(default_factory=dict)
    raw_outputs: dict[str, Any] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)

    @classmethod
    def failed(
        cls,
        path: Path,
        fileizer: str,
        message: str,
        *,
        status: FileizerStatus = "failed",
        file_id: str | None = None,
    ) -> "FileizedDrawingRecord":
        from .utils import stable_file_id

        return cls(
            file_id=file_id or stable_file_id(path),
            source_path=str(path),
            relative_path=path.name,
            extension=path.suffix.lower(),
            fileizer=fileizer,
            status=status,
            errors=[message] if status == "failed" else [],
            warnings=[message] if status == "unavailable" else [],
        )
