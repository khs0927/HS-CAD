from __future__ import annotations

from pathlib import Path

import ezdxf

from src.remote_worker.job_schema import JobAction, RemoteDxfJob


def load_or_create_dxf(path: str | Path | None, allow_blank: bool = False) -> ezdxf.EzDxfDocument:
    if path and Path(path).exists():
        return ezdxf.readfile(str(path))
    if allow_blank:
        doc = ezdxf.new("R2010")
        doc.modelspace().add_lwpolyline([(0, 0), (6000, 0), (6000, 4000), (0, 4000), (0, 0)], dxfattribs={"layer": "GUIDE"})
        return doc
    raise FileNotFoundError(f"DXF source not found: {path}")


def ensure_layer(doc: ezdxf.EzDxfDocument, name: str, color: int | None = None) -> None:
    if name not in doc.layers:
        doc.layers.add(name=name, color=color or 7)
    elif color is not None:
        doc.layers.get(name).dxf.color = color


def add_text_note(doc: ezdxf.EzDxfDocument, action: JobAction) -> None:
    layer = action.layer or "DIMLE"
    ensure_layer(doc, layer, action.color)
    x, y = action.position or (0, 0)
    height = float(action.params.get("height", 120))
    doc.modelspace().add_text(
        action.text or "",
        dxfattribs={"layer": layer, "height": height},
    ).set_placement((x, y))


def add_leader_note(doc: ezdxf.EzDxfDocument, action: JobAction) -> None:
    layer = action.layer or "DIMLE"
    ensure_layer(doc, layer, action.color)
    start = action.position or (0, 0)
    end = action.leader_to or start
    doc.modelspace().add_line(start, end, dxfattribs={"layer": layer})
    add_text_note(doc, action)


def apply_action(doc: ezdxf.EzDxfDocument, action: JobAction) -> str:
    if action.type == "inspect_only":
        return "inspect_only"
    if action.type == "ensure_layer":
        ensure_layer(doc, action.layer or "DIMLE", action.color)
        return f"ensure_layer:{action.layer or 'DIMLE'}"
    if action.type == "add_text_note":
        add_text_note(doc, action)
        return f"add_text_note:{action.text}"
    if action.type == "add_leader_note":
        add_leader_note(doc, action)
        return f"add_leader_note:{action.text}"
    if action.type == "normalize_layer_color":
        ensure_layer(doc, action.layer or "0", action.color or 7)
        return f"normalize_layer_color:{action.layer}"
    raise ValueError(f"unsupported action: {action.type}")


def save_modified_dxf(job: RemoteDxfJob, source_path: str | Path | None, out_path: str | Path) -> list[str]:
    doc = load_or_create_dxf(source_path, allow_blank=job.source.allow_blank)
    changes = [apply_action(doc, action) for action in job.actions]
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    doc.saveas(str(out))
    return changes
