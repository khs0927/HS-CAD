"""Failure tracking utilities for corpus‑run."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

from .models import CorpusRunFailure


def _fail_path(workspace: Path) -> Path:
    return workspace / "failures" / "failed_files.json"


def _retry_path(workspace: Path) -> Path:
    return workspace / "failures" / "retry_queue.json"


def load_failures(workspace: Path) -> List[CorpusRunFailure]:
    p = _fail_path(workspace)
    if not p.exists():
        return []
    data = json.loads(p.read_text(encoding="utf-8"))
    return [CorpusRunFailure(**d) for d in data]


def save_failures(workspace: Path, failures: List[CorpusRunFailure]) -> None:
    p = _fail_path(workspace)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps([f.dict() for f in failures], ensure_ascii=False, indent=2), encoding="utf-8")


def record_failure(workspace: Path, file_id: str, error: str) -> None:
    failures = load_failures(workspace)
    # Increment attempts if already present
    for f in failures:
        if f.file_id == file_id:
            f.attempts += 1
            f.error = error
            break
    else:
        failures.append(CorpusRunFailure(file_id=file_id, error=error))
    save_failures(workspace, failures)


def build_retry_queue(workspace: Path, limit: int | None = None) -> List[CorpusRunFailure]:
    failures = load_failures(workspace)
    retry = [f for f in failures if not f.permanent]
    if limit is not None:
        retry = retry[:limit]
    # write retry queue file for visibility
    p = _retry_path(workspace)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps([f.dict() for f in retry], ensure_ascii=False, indent=2), encoding="utf-8")
    return retry


def mark_permanent(workspace: Path, file_id: str) -> None:
    failures = load_failures(workspace)
    for f in failures:
        if f.file_id == file_id:
            f.permanent = True
    save_failures(workspace, failures)


def summarize_failures(workspace: Path) -> Dict[str, Any]:
    failures = load_failures(workspace)
    total = len(failures)
    per_ext: Dict[str, int] = {}
    top_errors: Dict[str, int] = {}
    for f in failures:
        ext = f.file_id.split('.')[-1] if '.' in f.file_id else ''
        per_ext[ext] = per_ext.get(ext, 0) + 1
        top_errors[f.error] = top_errors.get(f.error, 0) + 1
    # top N errors
    top_errors = dict(sorted(top_errors.items(), key=lambda x: -x[1])[:5])
    return {"total": total, "by_extension": per_ext, "top_errors": top_errors}
