"""Pipeline runner for the operational corpus‑run workflow.

Provides high‑level functions that are invoked by the CLI sub‑app. Each step
updates the workspace manifest and progress files so that the run can be
resumed after interruption.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

from .failure_manager import summarize_failures, build_retry_queue
from .workspace import (
    create_workspace,
    load_config,
    load_manifest,
    save_manifest,
    update_progress,
    load_progress,
)
from .stage_fileize import fileize_run_files
from .stage_index import run_index
from .stage_learn import run_learn
from .stage_audit import run_audit
from .stage_query import run_query as _stage_query
from .stage_report import run_report as _stage_report


def run_prepare(root: str | Path, workspace: str | Path, sample: int = 0, overrides: Dict[str, Any] | None = None) -> None:
    """Create a fresh workspace based on *root*.

    *root* – source directory containing drawings.
    *workspace* – directory where all artefacts will live.
    *sample* – optional number of files to mark as pending initially.
    *overrides* – optional config overrides.
    """
    create_workspace(root, workspace, sample=sample, overrides=overrides)
    # Initial progress is zero processed
    update_progress(workspace, processed=0, total=load_manifest(workspace).files.__len__())


def _process_fileize(workspace: Path) -> Dict[str, Any]:
    """Run the fileize stage on all pending files.

    Returns the summary dict from ``fileize_run_files``.
    """
    config = load_config(workspace)
    manifest = load_manifest(workspace)
    # Files that have not yet been fileized
    pending = [f for f in manifest.files if f.status not in {"fileized", "indexed", "learned"}]
    summary = fileize_run_files(
        run_files=pending,
        root_path=config.root,
        fileized_out_dir=workspace / "fileized",
        force=False,
    )
    # Save updated manifest (statuses are updated inside fileize_run_files)
    save_manifest(workspace, manifest)
    # Update progress count based on fileized entries
    processed = len([f for f in manifest.files if f.status == "fileized"]) + len([f for f in manifest.files if f.status == "indexed"])  # simplistic
    update_progress(workspace, processed=processed, total=len(manifest.files))
    return summary


def run_execute(workspace: str | Path, limit: int | None = None, force: bool = False) -> dict:
    """Execute the main pipeline steps: fileize → index → learn.

    Returns a dict with ``fileize``, ``index`` and ``learn`` keys containing the
    respective stage results.
    """
    ws = Path(workspace)
    # Fileize stage (process pending files)
    fileize_summary = _process_fileize(ws)

    # Index stage – ingests all fileized JSONs (or limit)
    index_stats = run_index(ws, limit=limit, force=force)

    # Learning stage – generates summary lessons
    learn_summary = run_learn(ws)

    return {"fileize": fileize_summary, "index": index_stats, "learn": learn_summary}


def run_continue(workspace: str | Path, limit: int | None = None, force: bool = False) -> dict:
    """Continue a previously interrupted run.

    Re‑runs ``run_execute`` which will only process files that are still not
    indexed.
    """
    return run_execute(workspace, limit=limit, force=force)


def execute_query(workspace: str | Path, query: str, limit: int = 30) -> dict:
    """Execute a query against the indexed corpus.

    Returns the evidence pack dict.
    """
    return _stage_query(workspace, query=query, limit=limit)


def generate_report(workspace: str | Path, company_profile_path: str | None = None) -> dict:
    """Generate the final markdown report for the run.
    """
    return _stage_report(workspace, company_profile_path=company_profile_path)


def run_failures(workspace: str | Path) -> dict:
    """Return a summary of recorded file‑level failures.
    """
    return summarize_failures(Path(workspace))


def run_retry_failures(workspace: str | Path, limit: int | None = None) -> dict:
    """Retry failed fileize operations.

    *limit* – optional cap on the number of retries.
    Returns the summary dict from the retry fileize run.
    """
    ws = Path(workspace)
    # Build retry queue (updates failures JSON)
    retry_items = build_retry_queue(ws, limit=limit)
    if not retry_items:
        return {"retry": []}
    # Load manifest and config to resolve source paths
    config = load_config(ws)
    manifest = load_manifest(ws)
    retry_ids = {f.file_id for f in retry_items}
    retry_files = [f for f in manifest.files if f.file_id in retry_ids]
    # Re‑run fileize on the selected files (force=True to overwrite)
    summary = fileize_run_files(
        run_files=retry_files,
        root_path=config.root,
        fileized_out_dir=ws / "fileized",
        force=True,
    )
    # Save manifest changes after retry
    save_manifest(ws, manifest)
    return {"retry_summary": summary}
