from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.corpus.schema import FileizedDrawingRecord
from src.semantic_index.features import FEATURE_VERSION, GeometryFeatureExtractor
from src.semantic_index.schema import SearchHit, SemanticVector
from src.semantic_index.store import SemanticIndexStore


class SemanticIndexService:
    def __init__(self, sqlite_path: str | Path):
        self.store = SemanticIndexStore(sqlite_path)
        self.extractor = GeometryFeatureExtractor()

    def build_from_json_dir(self, records_dir: str | Path, *, clear: bool = False) -> dict[str, Any]:
        root = Path(records_dir)
        if not root.exists():
            raise FileNotFoundError(root)
        if clear:
            self.store.clear(FEATURE_VERSION)

        indexed = 0
        skipped = 0
        empty_geometry: list[str] = []
        failures: list[dict[str, str]] = []
        for path in sorted(root.rglob('*.json')):
            try:
                record = load_record(path)
                if record.status != 'ok':
                    skipped += 1
                    continue
                vector = self.extractor.extract(record)
                if not _has_indexable_geometry(vector):
                    skipped += 1
                    empty_geometry.append(str(path))
                    continue
                self.store.upsert(vector)
                indexed += 1
            except Exception as exc:
                failures.append({'path': str(path), 'error': str(exc)})
        return {
            'feature_version': FEATURE_VERSION,
            'records_dir': str(root),
            'indexed': indexed,
            'skipped': skipped,
            'empty_geometry': empty_geometry,
            'failures': failures,
            'total_in_index': self.store.count(FEATURE_VERSION),
        }

    def search_record(self, record_path: str | Path, *, limit: int = 10, include_self: bool = False) -> list[SearchHit]:
        record = load_record(record_path)
        vector = self.extractor.extract(record)
        if not _has_indexable_geometry(vector):
            raise ValueError('query drawing has no indexable geometry after text removal')
        return self.store.search(
            vector,
            limit=limit,
            exclude_file_id=None if include_self else record.file_id,
        )

    def inspect(self) -> dict[str, Any]:
        return {
            'sqlite_path': str(self.store.sqlite_path),
            'feature_version': FEATURE_VERSION,
            'drawing_count': self.store.count(FEATURE_VERSION),
            'mode': 'offline-local',
            'text_used': False,
        }


def _has_indexable_geometry(vector: SemanticVector) -> bool:
    return any(abs(value) > 1e-12 for value in vector.vector)


def load_record(path: str | Path) -> FileizedDrawingRecord:
    source = Path(path)
    payload = json.loads(source.read_text(encoding='utf-8'))
    required = {'file_id', 'source_path', 'relative_path', 'extension', 'status', 'engine'}
    if not required.issubset(payload):
        missing = ', '.join(sorted(required.difference(payload)))
        raise ValueError(f'not a FileizedDrawingRecord; missing: {missing}')
    return FileizedDrawingRecord(**payload)
