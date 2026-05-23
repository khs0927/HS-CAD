from __future__ import annotations

import json
import sqlite3
from collections import Counter
from pathlib import Path


class CorpusLearner:
    def __init__(self, sqlite_path: str | Path):
        self.sqlite_path = Path(sqlite_path)

    def build_summary(self) -> dict:
        if not self.sqlite_path.exists():
            return {'status': 'missing_index', 'sqlite_path': str(self.sqlite_path)}
        with sqlite3.connect(str(self.sqlite_path)) as conn:
            conn.row_factory = sqlite3.Row
            counts = {name: conn.execute(f'SELECT count(*) FROM {name}').fetchone()[0] for name in ('files', 'layers', 'entities', 'texts', 'blocks', 'dimensions', 'failures')}
            entity_types = [dict(row) for row in conn.execute('SELECT entity_type, count(*) AS count FROM entities GROUP BY entity_type ORDER BY count DESC LIMIT 50')]
            layer_rows = [dict(row) for row in conn.execute('SELECT name, sum(entity_count) AS count FROM layers GROUP BY name ORDER BY count DESC LIMIT 50')]
            block_rows = [dict(row) for row in conn.execute('SELECT name, sum(count) AS count FROM blocks GROUP BY name ORDER BY count DESC LIMIT 50')]
            text_rows = [row['text'] for row in conn.execute('SELECT text FROM texts LIMIT 2000')]
        terms = Counter()
        for text in text_rows:
            for token in _tokens(text):
                terms[token] += 1
        return {
            'status': 'ok',
            'counts': counts,
            'top_entity_types': entity_types,
            'top_layers': layer_rows,
            'top_blocks': block_rows,
            'top_terms': [{'term': term, 'count': count} for term, count in terms.most_common(80)],
        }

    def write(self, out: str | Path) -> str:
        path = Path(out)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.build_summary(), ensure_ascii=False, indent=2), encoding='utf-8')
        return str(path)


def _tokens(text: str) -> list[str]:
    raw = str(text).replace('\n', ' ').replace('\t', ' ')
    out: list[str] = []
    for token in raw.split():
        cleaned = ''.join(ch for ch in token if ch.isalnum() or ch in {'-', '_', '/', '.'}).strip('.,;:()[]{}')
        if len(cleaned) >= 2:
            out.append(cleaned.lower())
    return out
