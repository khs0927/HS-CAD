from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel


def write_json(path: str | Path, data: BaseModel | dict) -> Path:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    payload = data.model_dump() if isinstance(data, BaseModel) else data
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return out

