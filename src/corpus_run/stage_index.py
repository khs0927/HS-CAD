"""Stage: index fileized JSON records into the knowledge store (SQLite)."""

from __future__ import annotations

from pathlib import Path

from src.corpus.fileized_ingest import ingest_fileized_folder

from .models import CorpusRunFile
from .workspace import load_manifest, save_manifest, load_config


def run_index(
    workspace: Path | str,
    limit: int | None = None,
    force: bool = False,
) -> dict:
    """Index fileized records.

    *workspace* – base directory of the run.
    *limit* – optional max number of fileized JSONs to process.
    *force* – currently unused, present for API compatibility.
    Returns the raw stats dict from ``ingest_fileized_folder``.
    """
    ws = Path(workspace)
    # Ensure required dirs exist (idempotent)
    fileized_root = ws / "fileized"
    kb_path = ws / "corpus" / "cad_knowledge.sqlite"
    stats = ingest_fileized_folder(fileized_root, kb_path, limit=limit)
    # Update manifest file statuses to "indexed" for successfully processed files
    manifest = load_manifest(ws)
    indexed_ids = {item.get("file_id") for item in stats.get("items", []) if isinstance(item, dict) and item.get("file_id")}
    for f in manifest.files:
        if f.file_id in indexed_ids:
            f.status = "indexed"
    save_manifest(ws, manifest)
    return stats
