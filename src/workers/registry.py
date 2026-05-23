from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class WorkerSpec:
    name: str
    worker_type: str
    env_manager: str
    python: str
    requirements: list[str]
    entry: str
    timeout_sec: int
    max_memory_mb: int | None = None
    gpu_required: bool = False
    outputs: list[str] = field(default_factory=list)
    status: str = 'implemented'

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class WorkerRegistry:
    def __init__(self, manifest_path: str | Path = 'config/worker_manifest.json'):
        self.manifest_path = Path(manifest_path)

    def load(self) -> dict[str, Any]:
        return json.loads(self.manifest_path.read_text(encoding='utf-8'))

    def specs(self) -> list[WorkerSpec]:
        payload = self.load()
        rows: list[WorkerSpec] = []
        for name, cfg in (payload.get('workers') or {}).items():
            rows.append(WorkerSpec(
                name=str(name),
                worker_type=str(cfg.get('worker_type') or 'unknown'),
                env_manager=str(cfg.get('env_manager') or 'current_python'),
                python=str(cfg.get('python') or ''),
                requirements=list(cfg.get('requirements') or []),
                entry=str(cfg.get('entry') or ''),
                timeout_sec=int(cfg.get('timeout_sec') or 300),
                max_memory_mb=cfg.get('max_memory_mb'),
                gpu_required=bool(cfg.get('gpu_required') or False),
                outputs=list(cfg.get('outputs') or []),
                status=str(cfg.get('status') or 'implemented'),
            ))
        return rows

    def get(self, name: str) -> WorkerSpec | None:
        for spec in self.specs():
            if spec.name == name:
                return spec
        return None

    def summary(self) -> dict[str, Any]:
        specs = self.specs()
        type_counts: dict[str, int] = {}
        status_counts: dict[str, int] = {}
        for spec in specs:
            type_counts[spec.worker_type] = type_counts.get(spec.worker_type, 0) + 1
            status_counts[spec.status] = status_counts.get(spec.status, 0) + 1
        return {
            'manifest_path': str(self.manifest_path),
            'worker_count': len(specs),
            'type_counts': type_counts,
            'status_counts': status_counts,
            'workers': [spec.to_dict() for spec in specs],
        }
