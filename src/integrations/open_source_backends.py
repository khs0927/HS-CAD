from __future__ import annotations

import importlib.util
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


@dataclass
class BackendStatus:
    id: str
    capability: str
    python_import: str
    required: bool
    available: bool
    reason: str
    purpose: str = ''
    planned_pr: str = ''

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class OpenSourceBackendRegistry:
    def __init__(self, config_path: str | Path = 'config/open_source_backends.json'):
        self.config_path = Path(config_path)

    def load(self) -> dict[str, Any]:
        return json.loads(self.config_path.read_text(encoding='utf-8'))

    def statuses(self) -> list[BackendStatus]:
        payload = self.load()
        rows: list[BackendStatus] = []
        for backend in payload.get('backends', []):
            import_name = str(backend.get('python_import') or '')
            available = importlib.util.find_spec(import_name) is not None if import_name else False
            rows.append(BackendStatus(
                id=str(backend.get('id') or ''),
                capability=str(backend.get('capability') or ''),
                python_import=import_name,
                required=bool(backend.get('required', False)),
                available=available,
                reason='installed' if available else 'not installed',
                purpose=str(backend.get('purpose') or ''),
                planned_pr=str(backend.get('planned_pr') or ''),
            ))
        return rows

    def summary(self) -> dict[str, Any]:
        statuses = self.statuses()
        return {
            'config_path': str(self.config_path),
            'backend_count': len(statuses),
            'available_count': sum(1 for item in statuses if item.available),
            'missing_optional_count': sum(1 for item in statuses if not item.available and not item.required),
            'missing_required_count': sum(1 for item in statuses if not item.available and item.required),
            'backends': [item.to_dict() for item in statuses],
        }
