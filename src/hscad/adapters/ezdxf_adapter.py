"""DXF adapter with optional ezdxf support and safe no-dependency fallback.

Policy:
- Reads DXF only; never mutates the original file.
- Writes only new review-output DXF files.
- Uses ezdxf when installed, otherwise a minimal ASCII DXF parser/writer.
- Does not call AutoCAD, ZWCAD, COM, SendCommand, or XiCAD aliases.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable

from hscad.core.models import DrawingEntity

SUPPORTED_MINIMAL_ENTITY_TYPES = {"LINE", "LWPOLYLINE", "POLYLINE", "TEXT", "MTEXT", "CIRCLE", "ARC", "INSERT", "HATCH"}


def _try_import_ezdxf():
    try:
        import ezdxf  # type: ignore
    except Exception:
        return None
    return ezdxf


def read_dxf_entities(path: str | Path) -> list[DrawingEntity]:
    dxf_path = Path(path)
    ezdxf = _try_import_ezdxf()
    if ezdxf is not None:
        try:
            return _read_with_ezdxf(dxf_path, ezdxf)
        except Exception:
            return _read_with_minimal_parser(dxf_path)
    return _read_with_minimal_parser(dxf_path)


def _xy(value: Any) -> tuple[float, float]:
    try:
        return (float(value[0]), float(value[1]))
    except Exception:
        return (0.0, 0.0)


def _common_raw(ent: Any, backend: str, doc: Any | None = None) -> dict[str, Any]:
    raw: dict[str, Any] = {"backend": backend, "handle": str(getattr(getattr(ent, "dxf", object()), "handle", ""))}
    if doc is not None:
        raw["dxfversion"] = str(getattr(doc, "dxfversion", ""))
    for attr in ("color", "linetype", "lineweight"):
        try:
            raw[attr] = getattr(ent.dxf, attr)
        except Exception:
            pass
    return raw


def _read_with_ezdxf(path: Path, ezdxf: Any) -> list[DrawingEntity]:
    doc = ezdxf.readfile(path)
    entities: list[DrawingEntity] = []
    for idx, ent in enumerate(doc.modelspace()):
        etype = ent.dxftype()
        layer = str(getattr(ent.dxf, "layer", "0") or "0")
        handle = str(getattr(ent.dxf, "handle", f"{idx:06d}") or f"{idx:06d}")
        geom: dict[str, Any] = {}
        text: str | None = None
        raw = _common_raw(ent, "ezdxf", doc)
        if etype == "LINE":
            geom = {"start": _xy(ent.dxf.start), "end": _xy(ent.dxf.end)}
        elif etype == "LWPOLYLINE":
            try:
                points = [(float(p[0]), float(p[1])) for p in ent.get_points()]
            except Exception:
                points = []
            geom = {"points": points, "closed": bool(getattr(ent, "closed", False))}
        elif etype == "POLYLINE":
            try:
                points = [(float(v.dxf.location.x), float(v.dxf.location.y)) for v in ent.vertices]
            except Exception:
                points = []
            geom = {"points": points, "closed": bool(getattr(ent, "is_closed", False))}
        elif etype == "TEXT":
            text = str(getattr(ent.dxf, "text", "") or "")
            geom = {"insert": _xy(getattr(ent.dxf, "insert", (0, 0, 0))), "height": float(getattr(ent.dxf, "height", 250.0) or 250.0)}
        elif etype == "MTEXT":
            try:
                text = str(ent.plain_text())
            except Exception:
                text = str(getattr(ent, "text", "") or "")
            geom = {"insert": _xy(getattr(ent.dxf, "insert", (0, 0, 0))), "height": float(getattr(ent.dxf, "char_height", 250.0) or 250.0)}
        elif etype == "CIRCLE":
            geom = {"center": _xy(ent.dxf.center), "radius": float(ent.dxf.radius)}
        elif etype == "ARC":
            geom = {"center": _xy(ent.dxf.center), "radius": float(ent.dxf.radius), "start_angle": float(ent.dxf.start_angle), "end_angle": float(ent.dxf.end_angle)}
        elif etype == "INSERT":
            geom = {"insert": _xy(getattr(ent.dxf, "insert", (0, 0, 0)))}
            raw["block_name"] = str(getattr(ent.dxf, "name", ""))
            raw["xscale"] = float(getattr(ent.dxf, "xscale", 1.0) or 1.0)
            raw["yscale"] = float(getattr(ent.dxf, "yscale", 1.0) or 1.0)
            raw["rotation"] = float(getattr(ent.dxf, "rotation", 0.0) or 0.0)
        elif etype == "HATCH":
            geom = {"points": []}
            try:
                boundary_points: list[tuple[float, float]] = []
                for path_item in ent.paths:
                    for edge in getattr(path_item, "edges", []):
                        if hasattr(edge, "start"):
                            boundary_points.append(_xy(edge.start))
                        if hasattr(edge, "end"):
                            boundary_points.append(_xy(edge.end))
                geom = {"points": boundary_points, "closed": True}
            except Exception:
                pass
        else:
            raw["unsupported_entity_type"] = etype
        entities.append(DrawingEntity(f"DXF-{idx:06d}", etype, layer, geom, text, {**raw, "handle": handle}, source=str(path)))
    return entities


def _group_pairs(path: Path) -> list[tuple[str, str]]:
    lines = path.read_text(errors="ignore", encoding="utf-8").splitlines()
    return [(lines[i].strip(), lines[i + 1].strip()) for i in range(0, len(lines) - 1, 2)]


def _read_with_minimal_parser(path: Path) -> list[DrawingEntity]:
    pairs = _group_pairs(path)
    entities: list[DrawingEntity] = []
    idx = 0
    i = 0
    while i < len(pairs):
        code, value = pairs[i]
        if code == "0" and value in SUPPORTED_MINIMAL_ENTITY_TYPES:
            etype = value
            raw: dict[str, Any] = {"backend": "minimal_dxf_parser"}
            i += 1
            fields: dict[str, list[str]] = {}
            while i < len(pairs) and not (pairs[i][0] == "0" and pairs[i][1] in SUPPORTED_MINIMAL_ENTITY_TYPES | {"ENDSEC", "EOF"}):
                c, v = pairs[i]
                fields.setdefault(c, []).append(v)
                i += 1
            layer = fields.get("8", ["0"])[0]
            raw.update({"handle": fields.get("5", [""])[0], "color": fields.get("62", [None])[0], "linetype": fields.get("6", [None])[0]})
            geom: dict[str, Any] = {}
            text: str | None = None
            if etype == "LINE":
                geom = {"start": (_f(fields, "10"), _f(fields, "20")), "end": (_f(fields, "11"), _f(fields, "21"))}
            elif etype in {"LWPOLYLINE", "POLYLINE"}:
                xs = [_safe_float(v) for v in fields.get("10", [])]
                ys = [_safe_float(v) for v in fields.get("20", [])]
                geom = {"points": list(zip(xs, ys)), "closed": fields.get("70", ["0"])[0] in {"1", "129"}}
            elif etype in {"TEXT", "MTEXT"}:
                text = " ".join(fields.get("1", []) or fields.get("3", []))
                geom = {"insert": (_f(fields, "10"), _f(fields, "20")), "height": _f(fields, "40", 250.0)}
            elif etype == "CIRCLE":
                geom = {"center": (_f(fields, "10"), _f(fields, "20")), "radius": _f(fields, "40")}
            elif etype == "ARC":
                geom = {"center": (_f(fields, "10"), _f(fields, "20")), "radius": _f(fields, "40"), "start_angle": _f(fields, "50"), "end_angle": _f(fields, "51")}
            elif etype == "INSERT":
                geom = {"insert": (_f(fields, "10"), _f(fields, "20"))}
                raw["block_name"] = fields.get("2", [""])[0]
                raw["rotation"] = _f(fields, "50")
            elif etype == "HATCH":
                xs = [_safe_float(v) for v in fields.get("10", [])]
                ys = [_safe_float(v) for v in fields.get("20", [])]
                geom = {"points": list(zip(xs, ys)), "closed": True}
            entities.append(DrawingEntity(f"DXF-{idx:06d}", etype, str(layer), geom, text, raw, source=str(path)))
            idx += 1
            continue
        i += 1
    return entities


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _f(fields: dict[str, list[str]], code: str, default: float = 0.0) -> float:
    return _safe_float(fields.get(code, [default])[0], default)


def write_review_dxf(path: str | Path, entities: Iterable[DrawingEntity], *, layer_descriptions: dict[str, str] | None = None) -> Path:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    entity_list = list(entities)
    ezdxf = _try_import_ezdxf()
    if ezdxf is not None:
        try:
            doc = ezdxf.new("R2010")
            msp = doc.modelspace()
            if layer_descriptions:
                for layer_name in sorted({e.layer for e in entity_list} | set(layer_descriptions)):
                    if layer_name and layer_name not in doc.layers:
                        doc.layers.add(layer_name)
            for entity in entity_list:
                _add_entity_ezdxf(msp, entity)
            doc.saveas(out)
            return out
        except Exception:
            return write_minimal_dxf(out, entity_list)
    return write_minimal_dxf(out, entity_list)


def _add_entity_ezdxf(msp: Any, entity: DrawingEntity) -> None:
    etype = entity.entity_type.upper()
    attribs = {"layer": entity.layer or "0"}
    if etype == "LINE":
        msp.add_line(entity.geometry.get("start", (0, 0)), entity.geometry.get("end", (0, 0)), dxfattribs=attribs)
    elif etype in {"LWPOLYLINE", "POLYLINE"}:
        msp.add_lwpolyline(entity.points, close=bool(entity.geometry.get("closed", False)), dxfattribs=attribs)
    elif etype in {"TEXT", "MTEXT"}:
        insert = entity.geometry.get("insert", (0, 0))
        height = float(entity.geometry.get("height", 250.0) or 250.0)
        msp.add_text(entity.text or "", dxfattribs={**attribs, "height": height}).set_placement(insert)
    elif etype == "CIRCLE":
        msp.add_circle(entity.geometry.get("center", (0, 0)), float(entity.geometry.get("radius", 0.0) or 0.0), dxfattribs=attribs)
    elif etype == "ARC":
        msp.add_arc(entity.geometry.get("center", (0, 0)), float(entity.geometry.get("radius", 0.0) or 0.0), float(entity.geometry.get("start_angle", 0.0) or 0.0), float(entity.geometry.get("end_angle", 0.0) or 0.0), dxfattribs=attribs)
    else:
        insert = entity.geometry.get("insert") or entity.geometry.get("center") or (0, 0)
        msp.add_text(f"UNSUPPORTED:{etype}", dxfattribs={**attribs, "height": 180}).set_placement(insert)


def write_minimal_dxf(path: str | Path, entities: Iterable[DrawingEntity]) -> Path:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    entity_list = list(entities)
    layers = sorted({e.layer or "0" for e in entity_list})
    lines: list[str] = ["0", "SECTION", "2", "HEADER", "9", "$ACADVER", "1", "AC1024", "0", "ENDSEC"]
    lines += ["0", "SECTION", "2", "TABLES", "0", "TABLE", "2", "LAYER", "70", str(len(layers))]
    for layer in layers:
        lines += ["0", "LAYER", "2", layer, "70", "0", "62", "7", "6", "CONTINUOUS"]
    lines += ["0", "ENDTAB", "0", "ENDSEC", "0", "SECTION", "2", "ENTITIES"]
    for entity in entity_list:
        etype = entity.entity_type.upper()
        layer = entity.layer or "0"
        if etype == "LINE":
            start = entity.geometry.get("start", (0, 0)); end = entity.geometry.get("end", (0, 0))
            lines += ["0", "LINE", "8", layer, "10", str(start[0]), "20", str(start[1]), "11", str(end[0]), "21", str(end[1])]
        elif etype in {"LWPOLYLINE", "POLYLINE"}:
            pts = entity.points
            lines += ["0", "LWPOLYLINE", "8", layer, "90", str(len(pts)), "70", "1" if entity.geometry.get("closed") else "0"]
            for x, y in pts:
                lines += ["10", str(x), "20", str(y)]
        elif etype in {"TEXT", "MTEXT"}:
            ins = entity.geometry.get("insert", (0, 0)); height = str(entity.geometry.get("height", 250.0) or 250.0)
            lines += ["0", "TEXT", "8", layer, "10", str(ins[0]), "20", str(ins[1]), "40", height, "1", entity.text or ""]
        elif etype == "CIRCLE":
            center = entity.geometry.get("center", (0, 0))
            lines += ["0", "CIRCLE", "8", layer, "10", str(center[0]), "20", str(center[1]), "40", str(entity.geometry.get("radius", 0.0))]
        elif etype == "ARC":
            center = entity.geometry.get("center", (0, 0))
            lines += ["0", "ARC", "8", layer, "10", str(center[0]), "20", str(center[1]), "40", str(entity.geometry.get("radius", 0.0)), "50", str(entity.geometry.get("start_angle", 0.0)), "51", str(entity.geometry.get("end_angle", 0.0))]
    lines += ["0", "ENDSEC", "0", "EOF"]
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out
