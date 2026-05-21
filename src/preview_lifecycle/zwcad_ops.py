import uuid
from pathlib import Path
from typing import Any


def connect_active_zwcad() -> tuple[Any, Any]:
    import win32com.client  # type: ignore

    app = win32com.client.GetActiveObject("ZWCAD.Application")
    return app, app.ActiveDocument


def send_command(doc: Any, command: str) -> bool:
    try:
        doc.SendCommand(command)
        return True
    except Exception:
        return False


def create_undo_mark(doc: Any) -> bool:
    return send_command(doc, "_.UNDO\n_M\n")


def erase_object_by_handle(doc: Any, handle: str) -> tuple[bool, str | None]:
    try:
        obj = doc.HandleToObject(handle)
    except Exception as exc:
        return False, f"failed to resolve handle {handle}: {exc}"
    try:
        obj.Delete()
        return True, None
    except Exception as exc:
        return False, f"failed to delete handle {handle}: {exc}"


def insert_block_from_dxf(doc: Any, source_dxf: str, base_point: list[float], scale: float, rotation: float, layer: str):
    try:
        doc.Layers.Item(layer)
    except Exception:
        try:
            doc.Layers.Add(layer)
        except Exception:
            pass
    source_path = str(Path(source_dxf).resolve())
    try:
        block_ref = doc.ModelSpace.InsertBlock(_variant_point(base_point), source_path, scale, scale, scale, rotation)
    except Exception:
        block_ref = _insert_dxf_as_isolated_preview_block(doc, source_path, base_point, scale, rotation, layer)
    try:
        block_ref.Layer = layer
    except Exception:
        pass
    return block_ref


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


def _insert_dxf_as_isolated_preview_block(doc: Any, source: str, base_point: list[float], scale: float, rotation: float, layer: str) -> Any:
    import ezdxf  # type: ignore

    source_path = Path(source)
    dxf = ezdxf.readfile(source_path)
    block_name = f"HS_PREVIEW_{source_path.stem}_{uuid.uuid4().hex[:8]}"
    block = doc.Blocks.Add(_variant_point((0, 0, 0)), block_name)
    for entity in dxf.modelspace():
        _copy_dxf_entity_to_block(block, entity, layer)
    ref = doc.ModelSpace.InsertBlock(_variant_point(base_point), block_name, scale, scale, scale, rotation)
    try:
        ref.Layer = layer
    except Exception:
        pass
    return ref
