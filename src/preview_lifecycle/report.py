import json
from pathlib import Path

from .schema import PreviewSession, to_dict


def write_json(obj, path: str | Path) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(to_dict(obj), ensure_ascii=False, indent=2), encoding="utf-8")


def write_session_md(session: PreviewSession, path: str | Path) -> None:
    lines = [
        "# Preview Session",
        "",
        f"- Session ID: {session.session_id}",
        f"- Status: {session.status}",
        f"- Source DXF: {session.source_dxf}",
        f"- Inserted handle: {session.inserted_handle}",
        f"- Insert layer: {session.insert_layer}",
        f"- Base point: {session.base_point}",
        f"- Scale: {session.scale}",
        f"- Rotation: {session.rotation}",
        f"- Undo mark created: {session.undo_mark_created}",
        f"- Saved: {session.saved}",
        "",
        "## Warnings",
    ]
    for warning in session.warnings or ["none"]:
        lines.append(f"- {warning}")
    lines += ["", "## Errors"]
    for error in session.errors or ["none"]:
        lines.append(f"- {error}")
    Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")
