"""Data models for the CAD corpus builder.

We use Pydantic v2 models to define the schema for files discovered
and for the knowledge records that will be stored in the knowledge
base. The models are deliberately lightweight – they only contain the
fields required for the core workflow and can be extended later.
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional

from pydantic import BaseModel, Field


class CorpusFile(BaseModel):
    """Metadata for a discovered file.

    The ``file_id`` is a stable SHA‑256 hash of the file path and size.
    ``status`` tracks the processing stage and ``error_message`` holds any
    exception information.
    """

    file_id: str = Field(..., description="Stable hash identifier")
    path: str = Field(..., description="Absolute path to the file")
    filename: str = Field(..., description="File name with extension")
    extension: str = Field(..., description="File extension without leading dot")
    size_bytes: int = Field(..., description="File size in bytes")
    modified_time: float = Field(..., description="POSIX timestamp of last modification")
    relative_path: str = Field(..., description="Path relative to the root folder")
    guessed_project_name: Optional[str] = Field(None, description="Heuristic project name")
    guessed_drawing_category: Optional[str] = Field(
        None, description="Heuristic drawing category (plan, section, etc.)"
    )
    status: str = Field(
        "pending",
        description="Processing status – pending, processing, done, failed, skipped",
    )
    error_message: Optional[str] = Field(None, description="Error details if failed")


class KnowledgeRecord(BaseModel):
    """A canonical knowledge entry extracted from an external drawing.

    The record is deliberately generic – downstream mappers can extend it.
    """

    record_id: str = Field(..., description="Unique identifier for the record")
    source_file_id: str = Field(..., description="Reference to the CorpusFile")
    situation_tags: List[str] = Field(default_factory=list)
    materials: List[dict] = Field(default_factory=list)
    specifications: List[dict] = Field(default_factory=list)
    dimensions: List[dict] = Field(default_factory=list)
    text_items: List[dict] = Field(default_factory=list)
    layer_summary: List[dict] = Field(default_factory=list)
    block_summary: List[dict] = Field(default_factory=list)
    lessons: List[str] = Field(default_factory=list)
    confidence: float = Field(0.0)
    warnings: List[str] = Field(default_factory=list)
