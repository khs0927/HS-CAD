from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path

SUPPORTED_EXTENSIONS = {'.dwg', '.dxf', '.pdf', '.png', '.jpg', '.jpeg', '.bmp', '.tif', '.tiff'}


@dataclass(frozen=True)
class ManifestEntry:
    file_id: str
    source_path: str
    relative_path: str
    extension: str
    size_bytes: int

    def to_dict(self) -> dict:
        return asdict(self)


def build_file_id(relative_path: str | Path) -> str:
    digest = hashlib.sha1(str(relative_path).replace('\\', '/').encode('utf-8')).hexdigest()
    return digest[:16]


def scan_manifest(root: str | Path, *, sample: int = 0, extensions: set[str] | None = None) -> list[ManifestEntry]:
    base = Path(root)
    allowed = extensions or SUPPORTED_EXTENSIONS
    rows: list[ManifestEntry] = []
    for path in sorted(base.rglob('*')):
        if not path.is_file():
            continue
        ext = path.suffix.lower()
        if ext not in allowed:
            continue
        rel = path.relative_to(base)
        rows.append(
            ManifestEntry(
                file_id=build_file_id(rel),
                source_path=str(path),
                relative_path=str(rel),
                extension=ext,
                size_bytes=path.stat().st_size,
            )
        )
        if sample and len(rows) >= sample:
            break
    return rows


def write_manifest(entries: list[ManifestEntry], out: str | Path) -> str:
    path = Path(out)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {'file_count': len(entries), 'files': [entry.to_dict() for entry in entries]}
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
    return str(path)


def read_manifest(path: str | Path) -> list[ManifestEntry]:
    payload = json.loads(Path(path).read_text(encoding='utf-8'))
    return [ManifestEntry(**row) for row in payload.get('files', [])]
