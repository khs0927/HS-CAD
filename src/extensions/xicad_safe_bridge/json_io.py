from __future__ import annotations

import json
from pathlib import Path

from .models import XicadSafeCommand


def load_safe_command(path: str | Path) -> XicadSafeCommand:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return XicadSafeCommand.model_validate(data)


def dump_plan_json(plan, path: str | Path) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(plan.model_dump_json(indent=2), encoding="utf-8")
