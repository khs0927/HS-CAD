from __future__ import annotations

import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def build_provenance(
    *,
    workspace: str | Path | None = None,
    backend: str | None = None,
    algorithm: str | None = None,
    source_artifacts: list[str] | None = None,
    worker_name: str | None = None,
    model_name: str | None = None,
    model_hash: str | None = None,
    backend_version: str | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'hscad_version': None,
        'git_commit': _git_commit(),
        'workspace': str(workspace) if workspace is not None else None,
        'backend': backend,
        'backend_version': backend_version,
        'algorithm': algorithm,
        'source_artifacts': source_artifacts or [],
        'model_name': model_name,
        'model_hash': model_hash,
        'worker_name': worker_name,
        'runtime': {
            'python': sys.version.split()[0],
            'platform': platform.platform(),
            'system': platform.system(),
            'machine': platform.machine(),
        },
    }
    if extra:
        payload.update(extra)
    return payload


def _git_commit() -> str | None:
    try:
        result = subprocess.run(
            ['git', 'rev-parse', 'HEAD'],
            capture_output=True,
            text=True,
            timeout=3,
            check=False,
        )
    except Exception:
        return None
    if result.returncode != 0:
        return None
    value = result.stdout.strip()
    return value or None
