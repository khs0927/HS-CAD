from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path


@dataclass(frozen=True)
class WorkerSpec:
    name: str
    path: str
    description: str = ""


class WorkerRegistry:
    def __init__(self, manifest_path: str | Path):
        self.manifest_path = Path(manifest_path)
        self._workers = self._load()

    def _load(self) -> dict[str, WorkerSpec]:
        if not self.manifest_path.exists():
            return {}
        payload = json.loads(self.manifest_path.read_text(encoding="utf-8"))
        workers = payload.get("workers") or {}
        specs: dict[str, WorkerSpec] = {}
        for name, row in workers.items():
            if not isinstance(row, dict):
                continue
            path = str(row.get("path") or row.get("module") or "")
            if path:
                specs[str(name)] = WorkerSpec(
                    name=str(name),
                    path=path,
                    description=str(row.get("description") or ""),
                )
        return specs

    def get(self, worker_name: str) -> WorkerSpec | None:
        return self._workers.get(worker_name)

    def names(self) -> list[str]:
        return sorted(self._workers)
