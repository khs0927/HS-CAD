from __future__ import annotations

import hashlib
from pathlib import Path


def stable_file_id(path: Path) -> str:
    """Stable ID based on absolute path + size + mtime when available.

    We avoid hashing full file bytes for speed on large DWG/PDF corpora.
    """
    p = Path(path)
    try:
        st = p.stat()
        seed = f"{p.resolve()}|{st.st_size}|{int(st.st_mtime)}"
    except OSError:
        seed = str(p)
    return hashlib.sha1(seed.encode("utf-8", errors="ignore")).hexdigest()[:16]


def normalize_text(value: str | None) -> str:
    if not value:
        return ""
    return " ".join(str(value).replace("\r", "\n").split())
