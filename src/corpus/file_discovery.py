"""Utilities for discovering files in a directory tree.

The implementation uses a generator to lazily walk the filesystem.  Hidden
files (starting with a dot) and temporary Office files prefixed with ``~$``
are skipped.  The caller can supply the list of extensions to consider – the
default list matches the specifications in the design document.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Generator, List, Iterable

DEFAULT_EXTENSIONS = {
    ".dwg",
    ".dxf",
    ".pdf",
    ".png",
    ".jpg",
    ".jpeg",
    ".tif",
    ".tiff",
    ".txt",
    ".csv",
    ".xlsx",
}


def _hash_file(path: Path) -> str:
    """Return a stable SHA‑256 hash for *path*.

    The hash is based on the absolute path and the file size – this is fast and
    deterministic for the purpose of identifying a file across runs.
    """

    h = hashlib.sha256()
    h.update(str(path.resolve()).encode("utf-8"))
    try:
        h.update(str(path.stat().st_size).encode("utf-8"))
    except Exception:
        pass
    return h.hexdigest()


def discover_files(
    root: Path,
    extensions: Iterable[str] | None = None,
) -> Generator[Path, None, None]:
    """Yield file paths under *root* that match *extensions*.

    ``extensions`` may be an iterable of lower‑case extensions (including the dot).
    If ``None`` the default set is used.
    """

    ext_set = set(extensions or DEFAULT_EXTENSIONS)
    for p in root.rglob("*"):
        if not p.is_file():
            continue
        if p.name.startswith("~$"):
            continue
        if p.name.startswith('.'):
            continue
        if p.suffix.lower() not in ext_set:
            continue
        yield p


def file_metadata(root: Path, file_path: Path) -> dict:
    """Return a dictionary with the required metadata for *file_path*.

    ``root`` is used to compute the relative path.
    """

    stat = file_path.stat()
    rel = file_path.relative_to(root)
    return {
        "file_id": _hash_file(file_path),
        "path": str(file_path.resolve()),
        "filename": file_path.name,
        "extension": file_path.suffix.lower().lstrip('.'),
        "size_bytes": stat.st_size,
        "modified_time": stat.st_mtime,
        "relative_path": str(rel),
        "guessed_project_name": None,
        "guessed_drawing_category": None,
        "status": "pending",
        "error_message": None,
    }
