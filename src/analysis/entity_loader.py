from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load_fileized_entities(workspace: str | Path) -> list[dict[str, Any]]:
    base = Path(workspace)
    rows: list[dict[str, Any]] = []
    json_dir = base / 'fileized' / 'json'
    if not json_dir.exists():
        return rows
    for path in sorted(json_dir.glob('*.json')):
        payload = read_json(path)
        file_id = str(payload.get('file_id') or path.stem)
        rel = str(payload.get('relative_path') or '')
        for idx, ent in enumerate(payload.get('entities') or []):
            if not isinstance(ent, dict):
                continue
            row = dict(ent)
            row.setdefault('id', f'{file_id}:{idx}')
            row['file_id'] = file_id
            row['relative_path'] = rel
            row['source_json'] = str(path)
            row['entity_index'] = idx
            row['entity_type'] = str(row.get('entity_type') or row.get('type') or '').upper()
            rows.append(row)
    return rows


def bbox_center(bbox: Any) -> tuple[float, float] | None:
    if not isinstance(bbox, list) or len(bbox) != 4:
        return None
    try:
        x1, y1, x2, y2 = [float(v) for v in bbox]
    except Exception:
        return None
    return ((x1 + x2) / 2.0, (y1 + y2) / 2.0)


def bbox_iou(a: Any, b: Any) -> float:
    if not (isinstance(a, list) and isinstance(b, list) and len(a) == 4 and len(b) == 4):
        return 0.0
    try:
        ax1, ay1, ax2, ay2 = [float(v) for v in a]
        bx1, by1, bx2, by2 = [float(v) for v in b]
    except Exception:
        return 0.0
    ix1, iy1 = max(ax1, bx1), max(ay1, by1)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    iw, ih = max(0.0, ix2 - ix1), max(0.0, iy2 - iy1)
    inter = iw * ih
    area_a = max(0.0, ax2 - ax1) * max(0.0, ay2 - ay1)
    area_b = max(0.0, bx2 - bx1) * max(0.0, by2 - by1)
    denom = area_a + area_b - inter
    return inter / denom if denom > 0 else 0.0


def distance(a: tuple[float, float] | None, b: tuple[float, float] | None) -> float | None:
    if a is None or b is None:
        return None
    return ((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2) ** 0.5


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        return {}


def write_json_and_md(base: Path, stem: str, payload: dict[str, Any], markdown: str | None = None) -> dict[str, Any]:
    (base / f'{stem}.json').write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
    (base / f'{stem}.md').write_text(markdown or f'# {stem}\n\n- Candidate count: `{len(payload.get("candidates") or payload.get("edges") or [])}`\n', encoding='utf-8')
    return payload
