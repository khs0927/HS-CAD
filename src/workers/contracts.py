from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field


WorkerStatus = Literal['ok', 'warning', 'error', 'unavailable', 'timeout']


class WorkerProvenance(BaseModel):
    generated_at: str | None = None
    hscad_version: str | None = None
    git_commit: str | None = None
    workspace: str | None = None
    backend: str | None = None
    backend_version: str | None = None
    algorithm: str | None = None
    source_artifacts: list[str] = Field(default_factory=list)
    model_name: str | None = None
    model_hash: str | None = None
    worker_name: str | None = None
    runtime: dict[str, Any] = Field(default_factory=dict)


class WorkerInput(BaseModel):
    protocol_version: str = '1.0'
    worker_name: str
    task: str
    workspace: str
    input_artifacts: list[str] = Field(default_factory=list)
    options: dict[str, Any] = Field(default_factory=dict)
    provenance: dict[str, Any] = Field(default_factory=dict)

    def to_json(self) -> str:
        return self.model_dump_json(indent=2)

    @classmethod
    def from_json_file(cls, path: str | Path) -> 'WorkerInput':
        return cls.model_validate_json(Path(path).read_text(encoding='utf-8'))

    def write_json(self, path: str | Path) -> Path:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(self.to_json(), encoding='utf-8')
        return target


class WorkerOutput(BaseModel):
    protocol_version: str = '1.0'
    worker_name: str
    backend: str
    status: WorkerStatus
    artifacts: list[str] = Field(default_factory=list)
    signals: list[dict[str, Any]] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    metrics: dict[str, Any] = Field(default_factory=dict)
    provenance: dict[str, Any] = Field(default_factory=dict)

    def to_json(self) -> str:
        return json.dumps(self.model_dump(), ensure_ascii=False, indent=2)

    @classmethod
    def ok(
        cls,
        *,
        worker_name: str,
        backend: str,
        artifacts: list[str] | None = None,
        signals: list[dict[str, Any]] | None = None,
        warnings: list[str] | None = None,
        metrics: dict[str, Any] | None = None,
        provenance: dict[str, Any] | None = None,
    ) -> 'WorkerOutput':
        return cls(
            worker_name=worker_name,
            backend=backend,
            status='ok',
            artifacts=artifacts or [],
            signals=signals or [],
            warnings=warnings or [],
            metrics=metrics or {},
            provenance=provenance or {},
        )

    @classmethod
    def error(
        cls,
        *,
        worker_name: str,
        backend: str,
        message: str,
        status: WorkerStatus = 'error',
        provenance: dict[str, Any] | None = None,
    ) -> 'WorkerOutput':
        return cls(
            worker_name=worker_name,
            backend=backend,
            status=status,
            warnings=[message],
            provenance=provenance or {},
        )
