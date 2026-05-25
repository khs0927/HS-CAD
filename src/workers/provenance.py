from __future__ import annotations

from pathlib import Path
from typing import Any


def build_provenance(
    *,
    workspace: str | Path,
    backend: str,
    algorithm: str,
    source_artifacts: list[str] | tuple[str, ...] | None = None,
    worker_name: str | None = None,
) -> dict[str, Any]:
    return {
        "worker_name": worker_name or backend,
        "backend": backend,
        "algorithm": algorithm,
        "workspace": str(workspace),
        "source_artifacts": list(source_artifacts or []),
        "safety": {
            "cad_mutation": False,
            "send_command": False,
            "original_dwg_mutation": False,
        },
    }
