"""Pydantic models for corpus‑run workspace and manifest."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, validator


class CorpusRunConfig(BaseModel):
    root: str
    workspace: str
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")
    sample_size: int = 0
    include_extensions: List[str] = Field(default_factory=lambda: [
        ".dwg", ".dxf", ".pdf", ".png", ".jpg", ".jpeg",
        ".tif", ".tiff", ".ifc", ".docx", ".pptx",
        ".xlsx", ".html", ".htm", ".txt",
    ])
    exclude_patterns: List[str] = Field(default_factory=list)
    read_only: bool = True
    anonymize_paths: bool = True
    max_file_size_mb: int = 500
    enable_ocr: bool = False
    enable_optional_fileizers: bool = False
    status: str = "prepared"

    @validator("sample_size")
    def non_negative(cls, v: int) -> int:
        return max(v, 0)


class CorpusRunFile(BaseModel):
    file_id: str
    relative_path: str
    extension: str
    size_bytes: int
    modified_time: float
    status: str = "discovered"
    attempts: int = 0
    last_error: Optional[str] = None
    outputs: Dict[str, Any] = Field(default_factory=dict)

    class Config:
        extra = "allow"


class CorpusRunManifest(BaseModel):
    files: List[CorpusRunFile] = Field(default_factory=list)

    def index_by_id(self) -> Dict[str, CorpusRunFile]:
        return {f.file_id: f for f in self.files}

    def get_pending(self) -> List[CorpusRunFile]:
        return [f for f in self.files if f.status in {"discovered", "fileized", "indexed"}]

    def update_file(self, updated: CorpusRunFile) -> None:
        for i, f in enumerate(self.files):
            if f.file_id == updated.file_id:
                self.files[i] = updated
                break


class CorpusRunProgress(BaseModel):
    processed: int = 0
    total: int = 0
    last_run: str = Field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")


class CorpusRunFailure(BaseModel):
    file_id: str
    error: str
    attempts: int = 1
    permanent: bool = False


class CorpusRunSummary(BaseModel):
    kb_path: str
    stats: Dict[str, Any] = Field(default_factory=dict)
    failures: List[CorpusRunFailure] = Field(default_factory=list)
