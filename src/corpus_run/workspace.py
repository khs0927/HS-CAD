"""Workspace utilities for the corpus‑run pipeline."""

from __future__ import annotations

import json
import os
import random
import shutil
from pathlib import Path
from typing import Any, Dict, List

from .models import CorpusRunConfig, CorpusRunFile, CorpusRunManifest


def _json_path(workspace: Path, name: str) -> Path:
    return workspace / name


def ensure_dirs(workspace: Path) -> None:
    """Create the required directory tree inside *workspace* if missing."""
    subdirs = [
        "fileized/json",
        "fileized/jsonl",
        "fileized/markdown",
        "corpus",
        "company_profile",
        "ops",
        "failures",
        "logs",
    ]
    for sub in subdirs:
        (workspace / sub).mkdir(parents=True, exist_ok=True)


def save_json(obj: Any, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def create_workspace(
    root: str | Path,
    workspace: str | Path,
    sample: int = 0,
    overrides: Dict[str, Any] | None = None,
) -> None:
    """Create a fresh workspace for a large corpus run.

    *root* – source folder containing drawing files.
    *workspace* – target directory where all generated artefacts live.
    *sample* – number of files to mark as active for the first run (0 = all).
    *overrides* – optional config values to replace defaults.
    """
    root_path = Path(root).resolve()
    work_path = Path(workspace).resolve()
    if work_path.exists():
        # never delete existing workspace – user may want to resume
        pass
    ensure_dirs(work_path)

    # Build config
    config = CorpusRunConfig(root=str(root_path), workspace=str(work_path), sample_size=sample)
    if overrides:
        config = config.copy(update=overrides)
    save_json(config.dict(), _json_path(work_path, "run_config.json"))

    # Scan source files
    files: List[CorpusRunFile] = []
    for p in root_path.rglob("*"):
        if not p.is_file():
            continue
        if p.suffix.lower() not in config.include_extensions:
            continue
        rel = p.relative_to(root_path)
        size = p.stat().st_size
        if size > config.max_file_size_mb * 1024 * 1024:
            continue
        file_id = f"{rel.as_posix()}"
        files.append(
            CorpusRunFile(
                file_id=file_id,
                relative_path=str(rel),
                extension=p.suffix.lower(),
                size_bytes=size,
                modified_time=p.stat().st_mtime,
            )
        )

    # Randomly pick sample files to mark as pending first, rest stay discovered
    if sample and sample < len(files):
        sampled = random.sample(files, sample)
        for f in files:
            if f in sampled:
                f.status = "pending"
            else:
                f.status = "discovered"
    else:
        for f in files:
            f.status = "pending"

    manifest = CorpusRunManifest(files=files)
    save_json([f.dict() for f in manifest.files], _json_path(work_path, "run_manifest.json"))
    # empty progress file
    save_json({"processed": 0, "total": len(files)}, _json_path(work_path, "progress.json"))


def load_config(workspace: str | Path) -> CorpusRunConfig:
    path = _json_path(Path(workspace), "run_config.json")
    return CorpusRunConfig(**load_json(path))


def load_manifest(workspace: str | Path) -> CorpusRunManifest:
    path = _json_path(Path(workspace), "run_manifest.json")
    data = load_json(path)
    return CorpusRunManifest(files=[CorpusRunFile(**d) for d in data])


def save_manifest(workspace: str | Path, manifest: CorpusRunManifest) -> None:
    path = _json_path(Path(workspace), "run_manifest.json")
    save_json([f.dict() for f in manifest.files], path)


def update_progress(workspace: str | Path, processed: int, total: int) -> None:
    path = _json_path(Path(workspace), "progress.json")
    save_json({"processed": processed, "total": total}, path)


def load_progress(workspace: str | Path) -> Dict[str, int]:
    path = _json_path(Path(workspace), "progress.json")
    return load_json(path)
