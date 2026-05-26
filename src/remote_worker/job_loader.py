from __future__ import annotations

import json
from pathlib import Path

from src.remote_worker.job_schema import RemoteDxfJob


def load_job(path: str | Path) -> RemoteDxfJob:
    job_path = Path(path)
    data = json.loads(job_path.read_text(encoding="utf-8"))
    return RemoteDxfJob.model_validate(data)
