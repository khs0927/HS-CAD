"""ezdxf adapter with a no-dependency fallback.

The fallback is intentionally small: it writes minimal ASCII DXF files and can
parse a few common entity tokens from simple DXF fixtures.  Production branches
should install ezdxf for robust DXF handling.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable

from hscad.core.models import DrawingEntity


def _try_import_ezdxf():
    try:
        import ezdxf  # type: ignore
    except Exception:  # pragma: no cover - depends on optional installation
        return None
    return ezdxf


def read_dxf_entities(path: str | Path) -> tuple[list[DrawingEntity], dict[str, Any]]:
    dxf_path = Path(path)
    ezdxf = _try_import_ezdxf()
    if ezdxf is not None:
        return _read_with_ezdxf(ezdxf, dxf_path)
    return _read_with_minimal_parser(dxf_path)


def _read_with_ezdxf(ezdxf: Any, path: Path) -> tuple[list[DrawingEntity], dict[str, Any]]:
    doc = ezdxf.readfile(path)
    msp = doc.modelspace()
    entities: list[DrawingEntity] = []
    for idx, entity in enumerate(msp):
        dxftype = entity.dxftype()
        layer = getattr(entity.dxf, "layer", "0")
        geometry: dict[str, Any] = {}
        text: str | None = None
        raw: dict[str, Any] = {"handle": getattr(entity.dxf, "handle", None)}
        if dxftype == "LINE":
            geometry = {"start": tuple(entity.dxf.start), "end": tuple(entity.dxf.end)}
        elif dxftype in {"LWPOLYLINE", "POLYLINE"}:
            try:
                geometry = {"points": [tuple(p[:2]) for p in entity.get_points()]}
            except Exception:
                geometry = {"points": []}
        elif dxftype in {"TEXT", "MTEXT"}:
            text = getattr(entity.dxf, "text", None) or getattr(entity, "text", None)
            geometry = {"insert": tuple(getattr(entity.dxf, "insert", (0, 0, 0)))}
        elif dxftype == "CIRCLE":
            geometry = {"center": tuple(entity.dxf.center), "radius": float(entity.dxf.radius)}
        elif dxftype == "ARC":
            geometry = {
                "center": tuple(entity.dxf.center),
                "radius": float(entity.dxf.radius),
                "start_angle": float(entity.dxf.start_angle),
                "end_angle": float(entity.dxf.end_angle),
            }
        entities.append(
            DrawingEntity(
                entity_id=f"DXF-{idx:06d}",
                entity_type=dxftype,
                layer=str(layer),
                geometry=geometry,
                text=text,
                raw=raw,
            )
        )
    return entities, {"backend": "ezdxf", "dxfversion": doc.dxfversion}


def _read_with_minimal_parser(path: Path) -> tuple[list[DrawingEntity], dict[str, Any]]:
    text = path.read_text(encoding="utf-8", errors="ignore")
    lines = [line.strip() for line in text.splitlines()]
    entities: list[DrawingEntity] = []
    idx = 0
    i = 0
    while i < len(lines):
        token = lines[i].upper()
        if token in {"LINE", "TEXT", "MTEXT", "LWPOLYLINE", "POLYLINE", "CIRCLE", "ARC"}:
            layer = "0"
            # DXF group code 8 is layer. The following value is the layer name.
            for j in range(i, min(i + 80, len(lines) - 1)):
                if lines[j] == "8":
                    layer = lines[j + 1]
                    break
            entities.append(
                DrawingEntity(
                    entity_id=f"DXF-FALLBACK-{idx:06d}",
                    entity_type=token,
                    layer=layer,
                    raw={"parser": "minimal_text_parser", "line_index": i},
                )
            )
            idx += 1
        i += 1
    return entities, {"backend": "minimal_text_parser", "entity_count": len(entities)}


def write_minimal_dxf(path: str | Path, entities: Iterable[DrawingEntity]) -> Path:
    """Write a minimal DXF containing LINE/TEXT-ish entities.

    This is not a full CAD writer. It exists so CI and plan-only flows can produce
    deterministic artifacts even when ezdxf is unavailable.
    """
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    parts: list[str] = ["0", "SECTION", "2", "ENTITIES"]
    for ent in entities:
        layer = ent.layer or "0"
        if ent.entity_type.upper() == "TEXT" or ent.text:
            insert = ent.geometry.get("insert", (0, 0, 0)) if ent.geometry else (0, 0, 0)
            x, y = float(insert[0]), float(insert[1])
            parts += ["0", "TEXT", "8", layer, "10", str(x), "20", str(y), "40", "250", "1", ent.text or ent.entity_id]
        else:
            start = ent.geometry.get("start", (0, 0, 0)) if ent.geometry else (0, 0, 0)
            end = ent.geometry.get("end", (1000, 0, 0)) if ent.geometry else (1000, 0, 0)
            parts += [
                "0", "LINE", "8", layer,
                "10", str(float(start[0])), "20", str(float(start[1])),
                "11", str(float(end[0])), "21", str(float(end[1])),
            ]
    parts += ["0", "ENDSEC", "0", "EOF"]
    out.write_text("\n".join(parts) + "\n", encoding="utf-8")
    return out


def write_dxf(path: str | Path, entities: Iterable[DrawingEntity]) -> Path:
    ezdxf = _try_import_ezdxf()
    if ezdxf is None:
        return write_minimal_dxf(path, entities)
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    doc = ezdxf.new("R2010")
    msp = doc.modelspace()
    for ent in entities:
        layer = ent.layer or "0"
        if layer not in doc.layers:
            doc.layers.add(layer)
        etype = ent.entity_type.upper()
        if etype == "TEXT" or ent.text:
            insert = ent.geometry.get("insert", (0, 0, 0)) if ent.geometry else (0, 0, 0)
            msp.add_text(ent.text or ent.entity_id, dxfattribs={"layer": layer, "height": 250}).set_placement(insert)
        elif etype == "CIRCLE" and "center" in ent.geometry and "radius" in ent.geometry:
            msp.add_circle(ent.geometry["center"], ent.geometry["radius"], dxfattribs={"layer": layer})
        elif etype in {"LWPOLYLINE", "POLYLINE"} and ent.geometry.get("points"):
            msp.add_lwpolyline(ent.geometry["points"], dxfattribs={"layer": layer})
        else:
            start = ent.geometry.get("start", (0, 0, 0)) if ent.geometry else (0, 0, 0)
            end = ent.geometry.get("end", (1000, 0, 0)) if ent.geometry else (1000, 0, 0)
            msp.add_line(start, end, dxfattribs={"layer": layer})
    doc.saveas(out)
    return out
