from __future__ import annotations

import json
from abc import ABC, abstractmethod
from pathlib import Path

from src.corpus.schema import FileizedDrawingRecord


class DrawingFileizer(ABC):
    """Base interface for all HS-CAD fileizers."""

    engine_name = 'base'
    supported_extensions: tuple[str, ...] = ()

    def supports(self, path: str | Path) -> bool:
        return Path(path).suffix.lower() in self.supported_extensions

    def is_available(self) -> tuple[bool, str]:
        return True, 'available'

    @abstractmethod
    def fileize(self, path: str | Path, *, file_id: str, relative_path: str | Path) -> FileizedDrawingRecord:
        raise NotImplementedError


class FileizedRecordWriter:
    """Write stable JSON and light Markdown summaries for fileized records."""

    def __init__(self, root: str | Path):
        self.root = Path(root)
        self.json_dir = self.root / 'fileized' / 'json'
        self.md_dir = self.root / 'fileized' / 'markdown'
        self.failure_dir = self.root / 'failures'

    def write(self, record: FileizedDrawingRecord) -> dict[str, str]:
        self.json_dir.mkdir(parents=True, exist_ok=True)
        self.md_dir.mkdir(parents=True, exist_ok=True)
        self.failure_dir.mkdir(parents=True, exist_ok=True)

        json_path = self.json_dir / f'{record.file_id}.json'
        json_path.write_text(json.dumps(record.to_dict(), ensure_ascii=False, indent=2), encoding='utf-8')

        md_path = self.md_dir / f'{record.file_id}.md'
        md_path.write_text(self.to_markdown(record), encoding='utf-8')

        paths = {'json': str(json_path), 'markdown': str(md_path)}
        if record.status != 'ok':
            failure_path = self.failure_dir / f'{record.file_id}.json'
            failure_path.write_text(json.dumps(record.to_dict(), ensure_ascii=False, indent=2), encoding='utf-8')
            paths['failure'] = str(failure_path)
        return paths

    @staticmethod
    def to_markdown(record: FileizedDrawingRecord) -> str:
        lines = [
            f'# Fileized Drawing: {record.relative_path}',
            '',
            f'- File ID: `{record.file_id}`',
            f'- Status: `{record.status}`',
            f'- Engine: `{record.engine}`',
            f'- Extension: `{record.extension}`',
            f'- Entities: {len(record.entities)}',
            f'- Layers: {len(record.layers)}',
            f'- Blocks: {len(record.blocks)}',
            f'- Texts: {len(record.texts)}',
            f'- Dimensions: {len(record.dimensions)}',
            '',
        ]
        if record.warnings:
            lines.append('## Warnings')
            for item in record.warnings:
                lines.append(f'- {item}')
            lines.append('')
        if record.errors:
            lines.append('## Errors')
            for item in record.errors:
                lines.append(f'- {item}')
            lines.append('')
        if record.texts:
            lines.append('## Text samples')
            for row in record.texts[:30]:
                lines.append(f'- `{row.get("layer")}` {row.get("text")}')
            lines.append('')
        return '\n'.join(lines)
