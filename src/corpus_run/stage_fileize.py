"""Stage: fileize a batch of run files using absolute root path.

Implements the robust logic required for the operational pipeline – it never relies
on the current working directory.  All paths are resolved relative to the *root*
directory supplied by the run configuration.
"""

from __future__ import annotations

import traceback
from pathlib import Path
from typing import Any, Iterable

from src.drawing_fileizers.fileizer_registry import FileizerRegistry
from src.drawing_fileizers.fileized_record_writer import FileizedRecordWriter

from .models import CorpusRunFile
from .failure_manager import record_failure


def _get_file_id(run_file: Any) -> str:
    if isinstance(run_file, dict):
        return str(run_file.get("file_id", ""))
    return str(getattr(run_file, "file_id", ""))


def _get_relative_path(run_file: Any) -> str:
    if isinstance(run_file, dict):
        return str(run_file.get("relative_path", ""))
    return str(getattr(run_file, "relative_path", ""))


def _set_stage_status(run_file: Any, stage: str, status: str, error: str | None = None) -> None:
    """Compatibly update status fields on both Pydantic models and plain dicts."""
    if isinstance(run_file, dict):
        run_file["current_stage"] = stage
        run_file["status"] = status
        if error:
            run_file["last_error"] = error
        run_file["attempts"] = int(run_file.get("attempts", 0)) + 1
        return
    if hasattr(run_file, "current_stage"):
        setattr(run_file, "current_stage", stage)
    if hasattr(run_file, "status"):
        setattr(run_file, "status", status)
    if error and hasattr(run_file, "last_error"):
        setattr(run_file, "last_error", error)
    if hasattr(run_file, "attempts"):
        setattr(run_file, "attempts", int(getattr(run_file, "attempts", 0)) + 1)


def _fileized_json_path(fileized_out_dir: Path, file_id: str) -> Path:
    return fileized_out_dir / "json" / f"{file_id}.json"


def fileize_run_files(
    *,
    run_files: Iterable[Any],
    root_path: str | Path,
    fileized_out_dir: str | Path,
    force: bool = False,
) -> dict[str, Any]:
    """Fileize a batch of run files.

    *root_path* – path to the source directory (the original web‑hard location).
    *fileized_out_dir* – workspace sub‑folder where JSON records are stored.
    *force* – re‑fileize even if a JSON already exists.
    Returns a summary dict useful for logging / progress reporting.
    """
    root = Path(root_path).expanduser().resolve()
    out_dir = Path(fileized_out_dir).expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "json").mkdir(parents=True, exist_ok=True)
    (out_dir / "markdown").mkdir(parents=True, exist_ok=True)
    (out_dir / "tmp").mkdir(parents=True, exist_ok=True)

    registry = FileizerRegistry()
    writer = FileizedRecordWriter(out_dir)

    summary: dict[str, Any] = {
        "total": 0,
        "fileized": 0,
        "skipped": 0,
        "failed": 0,
        "unavailable": 0,
        "records": [],
        "errors": [],
    }

    for run_file in run_files:
        summary["total"] += 1
        file_id = _get_file_id(run_file)
        rel_path = _get_relative_path(run_file)
        if not file_id:
            summary["failed"] += 1
            summary["errors"].append({"file_id": "", "relative_path": rel_path, "error": "missing file_id"})
            continue
        if not rel_path:
            summary["failed"] += 1
            summary["errors"].append({"file_id": file_id, "relative_path": "", "error": "missing relative_path"})
            continue
        source_path = (root / rel_path).resolve()
        target_json = _fileized_json_path(out_dir, file_id)
        if target_json.exists() and not force:
            _set_stage_status(run_file, "fileize", "fileized")
            summary["skipped"] += 1
            summary["records"].append({"file_id": file_id, "source_path": str(source_path), "fileized_json": str(target_json), "status": "skipped_existing"})
            continue
        if not source_path.is_file():
            error = f"source file not found: {source_path}"
            _set_stage_status(run_file, "fileize", "failed", error)
            summary["failed"] += 1
            summary["errors"].append({"file_id": file_id, "relative_path": rel_path, "error": error})
            continue
        try:
            fileizer = registry.best_for(source_path)
            if fileizer is None:
                error = f"no available fileizer for extension: {source_path.suffix}"
                _set_stage_status(run_file, "fileize", "failed", error)
                summary["unavailable"] += 1
                summary["errors"].append({"file_id": file_id, "relative_path": rel_path, "error": error})
                continue
            record = fileizer.fileize(source_path, out_dir)
            # Align IDs with manifest entries
            try:
                record.file_id = file_id
                record.relative_path = rel_path
                record.source_path = str(source_path)
            except Exception:
                pass
            written = writer.write(record)
            status = getattr(record, "status", "success")
            if status in {"success", "partial"}:
                _set_stage_status(run_file, "fileize", "fileized")
                summary["fileized"] += 1
            elif status == "unavailable":
                _set_stage_status(run_file, "fileize", "failed", "fileizer unavailable")
                summary["unavailable"] += 1
            else:
                _set_stage_status(run_file, "fileize", "failed", "fileizer failed")
                summary["failed"] += 1
            summary["records"].append({
                "file_id": file_id,
                "source_path": str(source_path),
                "fileized_json": str(written.get("json", "")) if isinstance(written, dict) else "",
                "status": status,
            })
        except Exception as exc:
            error = f"{type(exc).__name__}: {exc}"
            _set_stage_status(run_file, "fileize", "failed", error)
            # Record failure centrally for later retry handling
            record_failure(out_dir.parent, file_id, error)
            summary["failed"] += 1
            summary["errors"].append({"file_id": file_id, "relative_path": rel_path, "source_path": str(source_path), "error": error})
    return summary

