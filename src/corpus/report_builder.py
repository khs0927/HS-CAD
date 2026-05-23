from __future__ import annotations

import sqlite3
from pathlib import Path


class CorpusReportBuilder:
    def __init__(self, sqlite_path: str | Path):
        self.sqlite_path = Path(sqlite_path)

    def build_markdown(self) -> str:
        if not self.sqlite_path.exists():
            return f'# HS-CAD Corpus Report\n\nIndex not found: `{self.sqlite_path}`\n'
        with sqlite3.connect(str(self.sqlite_path)) as conn:
            conn.row_factory = sqlite3.Row
            file_rows = conn.execute('SELECT status, engine, extension, count(*) AS count FROM files GROUP BY status, engine, extension ORDER BY status, engine, extension').fetchall()
            counts = {name: conn.execute(f'SELECT count(*) FROM {name}').fetchone()[0] for name in ('files', 'layers', 'entities', 'texts', 'blocks', 'dimensions', 'failures')}
            top_layers = conn.execute('SELECT name, sum(entity_count) AS count FROM layers GROUP BY name ORDER BY count DESC LIMIT 20').fetchall()
            top_blocks = conn.execute('SELECT name, sum(count) AS count FROM blocks GROUP BY name ORDER BY count DESC LIMIT 20').fetchall()
        lines = ['# HS-CAD Corpus Report', '']
        lines.append('## Summary')
        for key, value in counts.items():
            lines.append(f'- {key}: {value}')
        lines.append('')
        lines.append('## Files by status / engine / extension')
        for row in file_rows:
            lines.append(f'- {row["status"]} / {row["engine"]} / {row["extension"]}: {row["count"]}')
        lines.append('')
        lines.append('## Top layers')
        for row in top_layers:
            lines.append(f'- {row["name"]}: {row["count"]}')
        lines.append('')
        lines.append('## Top blocks')
        for row in top_blocks:
            lines.append(f'- {row["name"]}: {row["count"]}')
        lines.append('')
        return '\n'.join(lines)

    def write(self, out: str | Path) -> str:
        path = Path(out)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.build_markdown(), encoding='utf-8')
        return str(path)
