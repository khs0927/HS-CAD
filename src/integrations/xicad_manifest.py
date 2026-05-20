from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any
import hashlib
import json


@dataclass(frozen=True)
class FileRecord:
    path: str
    size: int
    sha256: str | None = None


def sha256_file(path: Path, *, max_bytes: int | None = None) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        remaining = max_bytes
        while True:
            if remaining is not None and remaining <= 0:
                break
            chunk_size = 1024 * 1024 if remaining is None else min(1024 * 1024, remaining)
            data = f.read(chunk_size)
            if not data:
                break
            h.update(data)
            if remaining is not None:
                remaining -= len(data)
    return h.hexdigest()


def build_manifest(root: str | Path, *, include_hashes: bool = False) -> dict[str, Any]:
    root_path = Path(root).expanduser().resolve()
    records: list[FileRecord] = []
    total_size = 0
    for file_path in sorted(root_path.rglob('*')):
        if not file_path.is_file():
            continue
        stat = file_path.stat()
        total_size += stat.st_size
        digest = sha256_file(file_path) if include_hashes else None
        records.append(FileRecord(str(file_path.relative_to(root_path)), stat.st_size, digest))
    by_ext: dict[str, int] = {}
    for record in records:
        ext = Path(record.path).suffix.lower() or '<no_ext>'
        by_ext[ext] = by_ext.get(ext, 0) + 1
    return {
        'root': str(root_path),
        'file_count': len(records),
        'total_size_bytes': total_size,
        'extensions': dict(sorted(by_ext.items())),
        'files': [asdict(record) for record in records],
    }


def write_manifest(root: str | Path, out: str | Path, *, include_hashes: bool = False) -> Path:
    data = build_manifest(root, include_hashes=include_hashes)
    out_path = Path(out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    return out_path
