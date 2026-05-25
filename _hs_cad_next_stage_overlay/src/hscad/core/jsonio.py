"""Small JSON utilities used by the next-stage overlay.

This module intentionally avoids project-wide dependencies so it can be copied into
older HS-CAD branches without causing import side effects.
"""
from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any


def to_plain_json(value: Any) -> Any:
    """Convert dataclasses and nested containers into JSON-serializable objects."""
    if is_dataclass(value):
        return to_plain_json(asdict(value))
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(k): to_plain_json(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [to_plain_json(v) for v in value]
    return value


def write_json(path: str | Path, data: Any) -> Path:
    """Write UTF-8 JSON with stable formatting and create parent directories."""
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(to_plain_json(data), ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    return out


def read_json(path: str | Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))
