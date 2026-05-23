from __future__ import annotations

import json
import sqlite3
from pathlib import Path


class EvidencePackageBuilder:
    def __init__(self, sqlite_path: str | Path):
        self.sqlite_path = Path(sqlite_path)

    def build(self, query: str, *, limit: int = 20) -> dict:
        text = query.strip()
        if not text:
            return {'query': query, 'evidence': [], 'warnings': [{'type': 'empty_query'}]}
        if not self.sqlite_path.exists():
            return {'query': query, 'evidence': [], 'warnings': [{'type': 'missing_index', 'path': str(self.sqlite_path)}]}
        with sqlite3.connect(str(self.sqlite_path)) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                '''
                SELECT f.file_id, f.source_path, f.relative_path, t.handle, t.layer, t.entity_type, t.text, t.payload_json
                FROM texts t
                JOIN files f ON f.file_id = t.file_id
                WHERE t.text LIKE ?
                LIMIT ?
                ''',
                (f'%{text}%', limit),
            ).fetchall()
        evidence = []
        for index, row in enumerate(rows, start=1):
            payload = {}
            try:
                payload = json.loads(row['payload_json']) if row['payload_json'] else {}
            except Exception:
                payload = {'raw': row['payload_json']}
            evidence.append(
                {
                    'rank': index,
                    'evidence_type': 'text',
                    'file_id': row['file_id'],
                    'source_path': row['source_path'],
                    'relative_path': row['relative_path'],
                    'handle': row['handle'],
                    'layer': row['layer'],
                    'entity_type': row['entity_type'],
                    'text': row['text'],
                    'bbox': payload.get('bbox'),
                    'insert': payload.get('insert'),
                    'page_number': payload.get('page_number'),
                }
            )
        return {'query': query, 'evidence': evidence, 'warnings': [] if evidence else [{'type': 'no_evidence'}]}
