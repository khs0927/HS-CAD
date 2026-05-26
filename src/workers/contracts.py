from __future__ import annotations

from dataclasses import asdict, dataclass, field
import json
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class WorkerInput:
    worker_name: str
    task: str
    workspace: str
    input_artifacts: list[str] = field(default_factory=list)
    options: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)

    @classmethod
    def from_json_file(cls, path: str | Path) -> "WorkerInput":
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls(
            worker_name=str(payload.get("worker_name") or ""),
            task=str(payload.get("task") or "run"),
            workspace=str(payload.get("workspace") or "."),
            input_artifacts=[str(item) for item in payload.get("input_artifacts") or []],
            options=dict(payload.get("options") or {}),
        )


@dataclass(frozen=True)
class WorkerOutput:
    worker_name: str
    backend: str
    status: str
    artifacts: list[str] = field(default_factory=list)
    signals: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    metrics: dict[str, Any] = field(default_factory=dict)
    provenance: dict[str, Any] = field(default_factory=dict)
    error_message: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)

    @classmethod
    def error(
        cls,
        *,
        worker_name: str,
        backend: str,
        message: str,
        provenance: dict[str, Any] | None = None,
    ) -> "WorkerOutput":
        return cls(
            worker_name=worker_name,
            backend=backend,
            status="error",
            warnings=[message],
            provenance=provenance or {},
            error_message=message,
        )

    @classmethod
    def unavailable(
        cls,
        *,
        worker_name: str,
        backend: str,
        message: str,
    ) -> "WorkerOutput":
        return cls(
            worker_name=worker_name,
            backend=backend,
            status="unavailable",
            warnings=[message],
        )
