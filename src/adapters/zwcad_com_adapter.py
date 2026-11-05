from __future__ import annotations

import importlib.util
import math
import os
import threading
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from src.app import logger
from src.cad_core.base import CADAdapter
from src.utils.geometry import chunk_points

# Windows-only COM modules are resolved lazily in _load_com() so tests can inject fakes
# and the module stays importable on Linux CI.
COM_AVAILABLE = importlib.util.find_spec("win32com") is not None


def _load_com() -> tuple[Any, Any]:
    """Return (win32com.client, pythoncom|None), importing lazily at call time."""
    try:
        import win32com.client as client
    except ImportError as exc:
        raise RuntimeError("COM support requires Windows OS with win32com / pythoncom.") from exc
    try:
        import pythoncom as pcom
    except ImportError:
        pcom = None
    return client, pcom


class ZWCADCOMAdapter(CADAdapter):
    """Enhanced ZWCAD COM Adapter following multiCAD-MCP connection & drawing patterns.

    Ensures live dynamic binding to the active GUI ZWCAD document (ActiveDocument),
    uses win32com VARIANT arrays for seamless COM entity creation, and provides
    real-time view updates (Regen & ZoomExtents) in the user's active viewport.
    """

    PROG_IDS: list[str] = [
        "ZWCAD.Application.2026",
        "ZWCAD.Application.2025",
        "ZWCAD.Application.2024",
        "ZWCAD.Application",
    ]
    VERSION_PROG_IDS: dict[str, tuple[str, ...]] = {
        "2026": ("ZWCAD.Application.2026", "ZWCAD.Application"),
        "2025": ("ZWCAD.Application.2025", "ZWCAD.Application"),
        "2024": ("ZWCAD.Application.2024", "ZWCAD.Application"),
    }

    def __init__(
        self,
        visible: bool = True,
        *,
        version: str | None = None,
        start_if_needed: bool = True,
    ) -> None:
        self.visible = visible
        self.version = version
        self.start_if_needed = start_if_needed
        self._local = threading.local()
        self.warnings: list[dict[str, Any]] = []
        self.active_progid: str | None = None

    def _candidate_progids(self) -> tuple[str, ...]:
        if self.version in self.VERSION_PROG_IDS:
            return self.VERSION_PROG_IDS[self.version]
        return tuple(self.PROG_IDS)

    @property
    def app(self) -> Any:
        return getattr(self._local, "app", None)

    @app.setter
    def app(self, value: Any) -> None:
        self._local.app = value

    @property
    def doc(self) -> Any:
        return getattr(self._local, "doc", None)

    @doc.setter
    def doc(self, value: Any) -> None:
        self._local.doc = value

    def connect(self) -> bool:
        """Connect to active ZWCAD application via COM (multiCAD-MCP pattern)."""
        client, pcom = _load_com()

        if pcom is not None:
            try:
                pcom.CoInitialize()
            except Exception:
                pass

        for progid in self._candidate_progids():
            try:
                self.app = client.GetActiveObject(progid)
                try:
                    self.app.Visible = True
                    self.app.Update()
                except Exception:
                    pass
                self.active_progid = progid
                logger.success(f"Connected to active ZWCAD GUI via GetActiveObject: {progid}")
                self._bind_active_document()
                return True
            except Exception:
                continue

        if self.start_if_needed:
            for progid in self._candidate_progids():
                try:
                    self.app = client.Dispatch(progid)
                    try:
                        self.app.Visible = self.visible
                        self.app.Update()
                    except Exception:
                        pass
                    self.active_progid = progid
                    logger.success(f"Spawned/Attached ZWCAD instance via Dispatch: {progid}")
                    self._bind_active_document()
                    return True
                except Exception:
                    continue

        if not self.start_if_needed:
            raise RuntimeError(
                "No running ZWCAD instance found and start_if_needed=False; refusing to spawn a new instance."
            )
        raise RuntimeError("Could not connect to ZWCAD COM interface.")

    def _bind_active_document(self) -> Any:
        if not self.app:
            return None
        try:
            if self.app.Documents.Count > 0:
                self.doc = self.app.ActiveDocument
            else:
                self.doc = self.app.Documents.Add()
            return self.doc
        except Exception as e:
            logger.warn(f"Failed to bind active document: {e}")
            return None

    def get_active_document(self) -> Any:
        if not self.app or not self.doc:
            self.connect()
        self._bind_active_document()
        return self.doc

    def open_document(self, path: str) -> Any:
        if not self.app:
            self.connect()
        abs_path = os.path.abspath(path).replace("/", "\\")
        self.doc = self.app.Documents.Open(abs_path)
        return self.doc

    def save_as(self, path: str) -> None:
        doc = self.get_active_document()
        if doc:
            doc.SaveAs(os.path.abspath(path))

    def close(self) -> None:
        if self.doc:
            try:
                self.doc.Close(False)
            except Exception:
                pass

    @staticmethod
    def _safe_get(obj: Any, attr: str, default: Any = None) -> Any:
        try:
            value = getattr(obj, attr)
            if isinstance(value, tuple):
                return list(value)
            return value
        except Exception:
            return default

    @staticmethod
    def _to_list(value: Any) -> list[Any]:
        if value is None:
            return []
        if isinstance(value, list):
            return value
        if isinstance(value, tuple):
            return list(value)
        try:
            return list(value)
        except Exception:
            return []

    @staticmethod
    def _entity_type(object_name: str) -> str:
        low = object_name.lower()
        if "lwpolyline" in low or "polyline" in low:
            return "POLYLINE"
        if "line" in low and "poly" not in low:
            return "LINE"
        if "mtext" in low:
            return "MTEXT"
        if "text" in low:
            return "TEXT"
        if "block" in low or "insert" in low:
            return "INSERT"
        if "circle" in low:
            return "CIRCLE"
        if "arc" in low:
            return "ARC"
        if "dim" in low:
            return "DIMENSION"
        return object_name.upper() if object_name else "UNKNOWN"

    def _read_attributes(self, obj: Any) -> list[dict[str, Any]]:
        try:
            if not bool(self._safe_get(obj, "HasAttributes", False)):
                return []
            attrs = obj.GetAttributes()
            rows: list[dict[str, Any]] = []
            for att in attrs:
                rows.append(
                    {
                        "tag": self._safe_get(att, "TagString"),
                        "text": self._safe_get(att, "TextString"),
                        "insert": self._to_list(self._safe_get(att, "InsertionPoint")),
                    }
                )
            return rows
        except Exception as exc:
            self.warnings.append({"type": "attribute_read_failed", "error": str(exc)})
            return []

    def _entity_to_dict(self, obj: Any) -> dict[str, Any]:
        object_name = str(self._safe_get(obj, "ObjectName", "") or "")
        entity_type = self._entity_type(object_name)
        item: dict[str, Any] = {
            "handle": self._safe_get(obj, "Handle"),
            "object_name": object_name,
            "entity_type": entity_type,
            "layer": self._safe_get(obj, "Layer"),
            "color": self._safe_get(obj, "Color"),
            "linetype": self._safe_get(obj, "Linetype"),
            "lineweight": self._safe_get(obj, "Lineweight"),
            "visible": self._safe_get(obj, "Visible"),
            "raw": {},
        }
        if entity_type == "LINE":
            item["start"] = self._to_list(self._safe_get(obj, "StartPoint"))
            item["end"] = self._to_list(self._safe_get(obj, "EndPoint"))
            item["length"] = self._safe_get(obj, "Length")
        elif entity_type == "POLYLINE":
            coords = self._to_list(self._safe_get(obj, "Coordinates"))
            item["coordinates"] = coords
            item["points"] = chunk_points(coords, 2)
            item["closed"] = self._safe_get(obj, "Closed")
            item["elevation"] = self._safe_get(obj, "Elevation")
        elif entity_type in {"TEXT", "MTEXT"}:
            item["insert"] = self._to_list(self._safe_get(obj, "InsertionPoint"))
            item["text"] = self._safe_get(obj, "TextString")
            item["height"] = self._safe_get(obj, "Height")
            item["rotation"] = self._safe_get(obj, "Rotation")
            item["style_name"] = self._safe_get(obj, "StyleName")
        elif entity_type == "INSERT":
            item["name"] = self._safe_get(obj, "Name")
            item["effective_name"] = self._safe_get(obj, "EffectiveName")
            item["insert"] = self._to_list(self._safe_get(obj, "InsertionPoint"))
            item["rotation"] = self._safe_get(obj, "Rotation")
            item["x_scale"] = self._safe_get(obj, "XScaleFactor")
            item["y_scale"] = self._safe_get(obj, "YScaleFactor")
            item["z_scale"] = self._safe_get(obj, "ZScaleFactor")
            item["attributes"] = self._read_attributes(obj)
        elif entity_type == "CIRCLE":
            item["center"] = self._to_list(self._safe_get(obj, "Center"))
            item["radius"] = self._safe_get(obj, "Radius")
        elif entity_type == "ARC":
            item["center"] = self._to_list(self._safe_get(obj, "Center"))
            item["radius"] = self._safe_get(obj, "Radius")
            item["start_angle"] = self._safe_get(obj, "StartAngle")
            item["end_angle"] = self._safe_get(obj, "EndAngle")
        elif entity_type == "DIMENSION":
            item["text_override"] = self._safe_get(obj, "TextOverride")
            item["measurement"] = self._safe_get(obj, "Measurement")
            item["text_position"] = self._to_list(self._safe_get(obj, "TextPosition"))
        return item

    def scan_modelspace(self) -> list[dict[str, Any]]:
        doc = self.get_active_document()
        self.warnings.clear()
        results: list[dict[str, Any]] = []
        if not doc:
            return results
        for obj in doc.ModelSpace:
            try:
                results.append(self._entity_to_dict(obj))
            except Exception as exc:
                warning = {
                    "object_name": self._safe_get(obj, "ObjectName"),
                    "handle": self._safe_get(obj, "Handle"),
                    "error": str(exc),
                }
                self.warnings.append(warning)
                results.append({"object_name": "ERROR", "entity_type": "ERROR", **warning})
        return results

    def _iter_modelspace(self) -> Iterable[Any]:
        doc = self.get_active_document()
        if doc:
            yield from doc.ModelSpace

    def _regen(self) -> None:
        try:
            doc = self.get_active_document()
            if doc:
                doc.Regen(1)
        except Exception:
            pass

    def move_entity(self, handle: str, dx: float, dy: float, dz: float = 0) -> int:
        moved = 0
        for obj in self._iter_modelspace():
            if str(self._safe_get(obj, "Handle")) == str(handle):
                obj.Move(self.vt_pt(0, 0, 0), self.vt_pt(dx, dy, dz))
                moved += 1
        if moved:
            self._regen()
        return moved

    def move_layer(self, layer: str, dx: float, dy: float, dz: float = 0) -> int:
        moved = 0
        for obj in self._iter_modelspace():
            try:
                if str(self._safe_get(obj, "Layer")) == layer:
                    obj.Move(self.vt_pt(0, 0, 0), self.vt_pt(dx, dy, dz))
                    moved += 1
            except Exception:
                continue
        if moved:
            self._regen()
        return moved

    def replace_text(self, find: str, replace: str, layer: str | None = None) -> int:
        changed = 0
        for obj in self._iter_modelspace():
            object_name = str(self._safe_get(obj, "ObjectName", "")).casefold()
            if "text" not in object_name:
                continue
            if layer and str(self._safe_get(obj, "Layer")) != layer:
                continue
            current = self._safe_get(obj, "TextString")
            if isinstance(current, str) and find in current:
                obj.TextString = current.replace(find, replace)
                changed += 1
        if changed:
            self._regen()
        return changed

    def delete_layer_objects(self, layer: str) -> int:
        targets = [obj for obj in self._iter_modelspace() if str(self._safe_get(obj, "Layer")) == layer]
        deleted = 0
        for obj in targets:
            try:
                obj.Delete()
                deleted += 1
            except Exception as exc:
                self.warnings.append(
                    {
                        "type": "delete_failed",
                        "handle": self._safe_get(obj, "Handle"),
                        "error": str(exc),
                    }
                )
        if deleted:
            self._regen()
        return deleted

    def run_command(self, command_text: str) -> None:
        text = str(command_text)
        if not text.strip():
            raise ValueError("command_text is empty")
        doc = self.get_active_document()
        if doc is None:
            raise RuntimeError("no active ZWCAD document")
        doc.SendCommand(text if text.endswith("\n") else text + "\n")

    def load_lisp(self, path: str) -> None:
        normalized = str(Path(path)).replace("\\", "/")
        self.run_command(f'(load "{normalized}")')

    def insert_block(
        self,
        block_name: str,
        insert: Iterable[float],
        layer: str = "0",
        rotation: float = 0,
        scale: Iterable[float] | None = None,
    ) -> Any:
        doc = self.get_active_document()
        if doc is None:
            raise RuntimeError("no active ZWCAD document")
        self.ensure_layer(layer)
        point = tuple(float(value) for value in insert)
        if len(point) < 2:
            raise ValueError("insert requires at least x and y")
        factors = tuple(float(value) for value in (scale or (1, 1, 1)))
        if len(factors) != 3:
            raise ValueError("scale requires x, y, and z factors")
        entity = doc.ModelSpace.InsertBlock(
            self.vt_pt(point[0], point[1], point[2] if len(point) > 2 else 0),
            block_name,
            factors[0],
            factors[1],
            factors[2],
            float(rotation),
        )
        entity.Layer = layer
        return entity

    def replace_block(
        self,
        target_block: str,
        new_block: str,
        layer: str | None = None,
    ) -> dict[str, Any]:
        matches = []
        for obj in self._iter_modelspace():
            object_name = str(self._safe_get(obj, "ObjectName", "")).casefold()
            if "block" not in object_name and "insert" not in object_name:
                continue
            name = self._safe_get(obj, "EffectiveName") or self._safe_get(obj, "Name")
            if str(name).casefold() != target_block.casefold():
                continue
            if layer and str(self._safe_get(obj, "Layer")) != layer:
                continue
            matches.append(obj)

        replaced = 0
        errors: list[dict[str, Any]] = []
        for obj in matches:
            try:
                insertion = tuple(float(value) for value in self._safe_get(obj, "InsertionPoint"))
                old_layer = str(self._safe_get(obj, "Layer", "0"))
                new_ref = self.insert_block(
                    new_block,
                    insertion,
                    layer=old_layer,
                    rotation=float(self._safe_get(obj, "Rotation", 0.0)),
                    scale=(
                        float(self._safe_get(obj, "XScaleFactor", 1.0)),
                        float(self._safe_get(obj, "YScaleFactor", 1.0)),
                        float(self._safe_get(obj, "ZScaleFactor", 1.0)),
                    ),
                )
                if new_ref is None:
                    raise RuntimeError("InsertBlock returned no entity")
                obj.Delete()
                replaced += 1
            except Exception as exc:
                errors.append(
                    {
                        "handle": self._safe_get(obj, "Handle"),
                        "error": str(exc),
                    }
                )
        if replaced:
            self._regen()
        return {
            "target_block": target_block,
            "new_block": new_block,
            "replaced": replaced,
            "errors": errors,
        }

    def list_layers(self) -> list[str]:
        doc = self.get_active_document()
        if not doc:
            return []
        return [lyr.Name for lyr in doc.Layers]

    def list_blocks(self) -> list[str]:
        doc = self.get_active_document()
        if not doc:
            return []
        return [blk.Name for blk in doc.Blocks]

    def vt_pt(self, x: float, y: float, z: float = 0.0) -> Any:
        client, pcom = _load_com()
        return client.VARIANT(pcom.VT_ARRAY | pcom.VT_R8, [float(x), float(y), float(z)])

    def vt_flat(self, coords: list[float]) -> Any:
        client, pcom = _load_com()
        return client.VARIANT(pcom.VT_ARRAY | pcom.VT_R8, [float(c) for c in coords])

    def ensure_layer(self, layer_name: str, color: int = 7) -> Any:
        doc = self.get_active_document()
        if not doc:
            return None
        try:
            lyr = doc.Layers.Item(layer_name)
        except Exception:
            try:
                lyr = doc.Layers.Add(layer_name)
            except Exception:
                return None
        try:
            if color is not None:
                lyr.Color = color
        except Exception:
            pass
        return lyr

    def create_line(
        self, start: tuple[float, float], end: tuple[float, float], layer: str = "0", color: int = 256
    ) -> Any:
        doc = self.get_active_document()
        self.ensure_layer(layer)
        p1 = self.vt_pt(start[0], start[1])
        p2 = self.vt_pt(end[0], end[1])
        line = doc.ModelSpace.AddLine(p1, p2)
        try:
            line.Layer = layer
            if color != 256:
                line.Color = color
        except Exception:
            pass
        return line

    def create_polyline(
        self, points: list[tuple[float, float]], layer: str = "0", closed: bool = True, color: int = 256
    ) -> Any:
        doc = self.get_active_document()
        self.ensure_layer(layer)
        flat = []
        for pt in points:
            flat.extend([float(pt[0]), float(pt[1])])
        poly = doc.ModelSpace.AddLightWeightPolyline(self.vt_flat(flat))
        try:
            poly.Closed = closed
            poly.Layer = layer
            if color != 256:
                poly.Color = color
        except Exception:
            pass
        return poly

    def create_text(
        self, text: str, insert: tuple[float, float], height: float = 300.0, layer: str = "0", color: int = 256
    ) -> Any:
        doc = self.get_active_document()
        self.ensure_layer(layer)
        t_pt = self.vt_pt(insert[0], insert[1])
        txt_ent = doc.ModelSpace.AddText(str(text), t_pt, float(height))
        try:
            txt_ent.Layer = layer
            if color != 256:
                txt_ent.Color = color
        except Exception:
            pass
        return txt_ent

    def create_circle(self, center: tuple[float, float], radius: float, layer: str = "0", color: int = 256) -> Any:
        doc = self.get_active_document()
        self.ensure_layer(layer)
        c_pt = self.vt_pt(center[0], center[1])
        c = doc.ModelSpace.AddCircle(c_pt, float(radius))
        try:
            c.Layer = layer
            if color != 256:
                c.Color = color
        except Exception:
            pass
        return c

    def create_dimension(
        self,
        p1: tuple[float, float],
        p2: tuple[float, float],
        dim_pt: tuple[float, float],
        rotation_deg: float = 0.0,
        layer: str = "A-DIM",
    ) -> Any:
        doc = self.get_active_document()
        self.ensure_layer(layer)
        pt1 = self.vt_pt(p1[0], p1[1])
        pt2 = self.vt_pt(p2[0], p2[1])
        pt_dim = self.vt_pt(dim_pt[0], dim_pt[1])
        try:
            d = doc.ModelSpace.AddDimRotated(pt1, pt2, pt_dim, math.radians(rotation_deg))
            d.Layer = layer
            return d
        except Exception:
            self.create_line(p1, p2, layer=layer)
            return None

    def refresh_view(self) -> None:
        """Regen and ZoomExtents in active ZWCAD viewport (multiCAD-MCP pattern)."""
        try:
            doc = self.get_active_document()
            if doc:
                doc.Regen(1)
        except Exception:
            pass
        try:
            if self.app:
                self.app.ZoomExtents()
                self.app.Update()
        except Exception:
            pass

    def list_texts(self) -> list[str]:
        """Return model-space TEXT and MTEXT values in scan order."""
        return [
            str(item["text"])
            for item in self.scan_modelspace()
            if (item.get("entity_type") or item.get("type")) in {"TEXT", "MTEXT"} and item.get("text") is not None
        ]
