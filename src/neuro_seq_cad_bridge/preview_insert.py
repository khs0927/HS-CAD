from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any


def connect_active_zwcad() -> tuple[Any, Any]:
    import win32com.client  # type: ignore

    app = win32com.client.GetActiveObject("ZWCAD.Application")
    return app, app.ActiveDocument


def _send_command(doc: Any, command: str) -> bool:
    try:
        doc.SendCommand(command)
        return True
    except Exception:
        return False


def create_undo_mark(doc: Any) -> bool:
    return _send_command(doc, "_.UNDO\n_M\n")


def undo_back(doc: Any) -> bool:
    _, doc = connect_active_zwcad()
    return _send_command(doc, "_.UNDO\n_B\n")


def _ensure_layer(doc: Any, layer_name: str) -> None:
    try:
        doc.Layers.Item(layer_name)
    except Exception:
        try:
            doc.Layers.Add(layer_name)
        except Exception:
            pass


def _pt3(point: Any) -> tuple[float, float, float]:
    values = list(point) if point is not None else [0, 0, 0]
    while len(values) < 3:
        values.append(0)
    return (float(values[0]), float(values[1]), float(values[2]))


def _variant_r8(values: list[float] | tuple[float, ...]):
    import pythoncom  # type: ignore
    from win32com.client import VARIANT  # type: ignore

    return VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_R8, [float(v) for v in values])


def _variant_point(point: Any):
    return _variant_r8(_pt3(point))


def _copy_dxf_entity_to_block(block: Any, entity: Any, layer: str) -> None:
    kind = entity.dxftype()
    try:
        if kind == "LINE":
            item = block.AddLine(_variant_point(entity.dxf.start), _variant_point(entity.dxf.end))
        elif kind == "LWPOLYLINE":
            coords: list[float] = []
            for x, y, *_ in entity.get_points():
                coords.extend([float(x), float(y)])
            if len(coords) < 4:
                return
            item = block.AddLightWeightPolyline(_variant_r8(coords))
            try:
                item.Closed = bool(entity.closed)
            except Exception:
                pass
        elif kind == "CIRCLE":
            item = block.AddCircle(_variant_point(entity.dxf.center), float(entity.dxf.radius))
        elif kind == "ARC":
            item = block.AddArc(_variant_point(entity.dxf.center), float(entity.dxf.radius), float(entity.dxf.start_angle), float(entity.dxf.end_angle))
        elif kind in {"TEXT", "MTEXT"}:
            text = entity.dxf.text if kind == "TEXT" else entity.text
            item = block.AddText(str(text), _variant_point(entity.dxf.insert), float(getattr(entity.dxf, "height", 250) or 250))
        else:
            return
        try:
            item.Layer = layer
        except Exception:
            pass
    except Exception:
        return


def _insert_dxf_as_isolated_preview_block(doc: Any, source: str, base: list[float], scale: float, rotation: float, layer: str) -> Any:
    import ezdxf  # type: ignore

    source_path = Path(source)
    dxf = ezdxf.readfile(source_path)
    block_name = f"HS_PREVIEW_{source_path.stem}_{uuid.uuid4().hex[:8]}"
    block = doc.Blocks.Add(_variant_point((0, 0, 0)), block_name)
    for entity in dxf.modelspace():
        _copy_dxf_entity_to_block(block, entity, layer)
    ref = doc.ModelSpace.InsertBlock(_variant_point(base), block_name, scale, scale, scale, rotation)
    try:
        ref.Layer = layer
    except Exception:
        pass
    return ref


def insert_dxf_preview(doc: Any, plan: dict[str, Any], allow_execute: bool = False) -> dict[str, Any]:
    result = {
        "operation": "insert_image_cad_preview",
        "allow_execute": allow_execute,
        "executed": False,
        "saved": False,
        "undo_mark_created": False,
        "inserted_handle": None,
        "warnings": list(plan.get("warnings") or []),
        "errors": [],
    }

    if not allow_execute:
        result["warnings"].append("allow_execute is false; dry-run only")
        return result

    if not plan.get("can_execute", True):
        result["errors"].append("plan.can_execute is false")
        return result

    source = plan.get("source_dxf")
    if not source or not Path(source).exists():
        result["errors"].append(f"source_dxf missing: {source}")
        return result

    try:
        result["undo_mark_created"] = create_undo_mark(doc)
        insert_layer = plan.get("insert_layer") or "QA-REVIEW"
        _ensure_layer(doc, insert_layer)

        base = plan.get("base_point") or [0, 0, 0]
        scale = float(plan.get("scale") or 1.0)
        rotation = float(plan.get("rotation") or 0.0)

        source_path = str(Path(source).resolve())
        try:
            # ZWCAD/AutoCAD COM often accepts external DWG paths as block names.
            block_ref = doc.ModelSpace.InsertBlock(_variant_point(base), source_path, scale, scale, scale, rotation)
        except Exception as first_exc:
            result["warnings"].append(f"external source InsertBlock failed; using isolated preview block fallback: {first_exc}")
            block_ref = _insert_dxf_as_isolated_preview_block(doc, source_path, base, scale, rotation, insert_layer)
        try:
            block_ref.Layer = insert_layer
        except Exception:
            pass
        result["inserted_handle"] = getattr(block_ref, "Handle", None)
        result["executed"] = True
    except Exception as exc:
        result["errors"].append(str(exc))

    return result


def write_insert_result(result: dict[str, Any], path: str | Path) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(result, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
