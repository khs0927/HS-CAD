import json
from pathlib import Path

from .schema import PreviewSession, to_dict


def save_preview_session(session: PreviewSession, path: str | Path) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(to_dict(session), ensure_ascii=False, indent=2), encoding="utf-8")


def load_preview_session(path: str | Path) -> PreviewSession:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return PreviewSession(**data)


def list_preview_sessions(directory: str | Path) -> list[Path]:
    d = Path(directory)
    if not d.exists():
        return []
    return sorted(d.rglob("preview_session*.json"))
