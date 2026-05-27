from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable

from src.app import logger
from src.cad_core.base import CADAdapter
from src.utils.geometry import chunk_points


class ZWCADCOMAdapter(CADAdapter):
    """ZWCAD COM/ActiveX adapter.

    The adapter is intentionally defensive: all Windows-only modules are imported
    lazily, every COM attribute access is guarded, and a single bad entity never
    stops a drawing scan. This keeps `--help` and pytest usable on non-ZWCAD
    machines while still providing an executable fallback on Windows.

    Parameters
    ----------
    visible:
        Whether a freshly spawned ZWCAD instance should be visible.
    version:
        Optional ZWCAD version pin. Accepts ``"2026"``, ``"2025"``,
        ``"2024"`` (mapped to legacy ProgIDs) or ``None`` to scan all
        known ProgIDs. The version pin affects which ProgIDs are
        attempted and the order in which they are tried.
    start_if_needed:
        If ``True`` (default) and no running ZWCAD instance is found,
        a new instance will be spawned via ``CreateObject``. If
        ``False``, only an already-running ZWCAD will be attached to
        and ``connect()`` will raise ``RuntimeError`` if none is
        available.
    """

    # Map known versions to candidate ProgIDs in priority order.
    _VERSION_PROGIDS: dict[str, list[str]] = {
        "2026": ["ZWCAD.Application.2026", "ZWCAD.Application"],
        "2025": ["ZWCAD.Application.2025", "ZWCAD.Application"],
        "2024": ["ZWCAD.Application.2024", "ZWCAD.Application"],
    }
    _DEFAULT_PROGIDS: list[str] = [
        "ZWCAD.Application.2026",
        "ZWCAD.Application.2025",
        "ZWCAD.Application.2024",
        "ZWCAD.Application",
    ]

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
        self.app: Any = None
        self.doc: Any = None
        self.active_progid: str | None = None
        self.warnings: list[dict[str, Any]] = []

    def _candidate_progids(self) -> list[str]:
        if self.version and self.version in self._VERSION_PROGIDS:
            return list(self._VERSION_PROGIDS[self.version])
        return list(self._DEFAULT_PROGIDS)

    def connect(self) -> None:
        progids = self._candidate_progids()

        # 1. Try win32com.client first for instantaneous dynamic dispatch (no freeze)
        try:
            import win32com.client
            # Try to attach first
            for progid in progids:
                try:
                    self.app = win32com.client.GetActiveObject(progid)
                    self.active_progid = progid
                    logger.success(f'Connected to active ZWCAD via win32com COM: {progid}')
                    return
                except Exception:
                    continue
            
            # Spawn if needed
            if self.start_if_needed:
                for progid in progids:
                    try:
                        self.app = win32com.client.Dispatch(progid)
                        try:
                            self.app.Visible = self.visible
                        except Exception:
                            pass
                        self.active_progid = progid
                        logger.success(f'Created new ZWCAD instance via win32com COM: {progid}')
                        return
                    except Exception:
                        continue
        except ImportError:
            pass

        # 2. Fall back to comtypes.client if win32com is not available
        import comtypes.client  # type: ignore

        # Try to attach to an already-running ZWCAD instance.
        for progid in progids:
            try:
                self.app = comtypes.client.GetActiveObject(progid)
                self.active_progid = progid
                logger.success(f'Connected to active ZWCAD via comtypes COM: {progid}')
                return
            except Exception:
                continue

        # Optionally spawn a new instance.
        if not self.start_if_needed:
            raise RuntimeError(
                'No running ZWCAD instance found and start_if_needed=False '
                f'(tried: {progids}).'
            )

        for progid in progids:
            try:
                self.app = comtypes.client.CreateObject(progid)
                try:
                    self.app.Visible = self.visible
                except Exception:
                    pass
                self.active_progid = progid
                logger.success(f'Created new ZWCAD instance via comtypes COM: {progid}')
                return
            except Exception:
                continue

        raise RuntimeError(
            'Failed to connect to ZWCAD COM. GetActiveObject and CreateObject '
            f'both failed for ProgIDs: {progids}.'
        )

    def open_document(self, path: str) -> Any:
        import os
        if self.app is None:
            self.connect()
        abs_path = os.path.abspath(path).replace('/', '\\')
        self.doc = self.app.Documents.Open(abs_path)
        return self.doc

    def get_active_document(self) -> Any:
        if self.app is None:
            self.connect()
        self.doc = self.app.ActiveDocument
        return self.doc

    def save_as(self, path: str) -> None:
        doc = self.doc or self.get_active_document()
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        doc.SaveAs(str(Path(path)))

    def close(self) -> None:
        try:
            if self.doc is not None:
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
        if 'lwpolyline' in low or 'polyline' in low:
            return 'POLYLINE'
        if 'line' in low and 'poly' not in low:
            return 'LINE'
        if 'mtext' in low:
            return 'MTEXT'
        if 'text' in low:
            return 'TEXT'
        if 'block' in low or 'insert' in low:
            return 'INSERT'
        if 'circle' in low:
            return 'CIRCLE'
        if 'arc' in low:
            return 'ARC'
        if 'dim' in low:
            return 'DIMENSION'
        return object_name.upper() if object_name else 'UNKNOWN'

    def _read_attributes(self, obj: Any) -> list[dict[str, Any]]:
        try:
            if not bool(self._safe_get(obj, 'HasAttributes', False)):
                return []
            attrs = obj.GetAttributes()
            rows: list[dict[str, Any]] = []
            for att in attrs:
                rows.append({
                    'tag': self._safe_get(att, 'TagString'),
                    'text': self._safe_get(att, 'TextString'),
                    'insert': self._to_list(self._safe_get(att, 'InsertionPoint')),
                })
            return rows
        except Exception as exc:
            self.warnings.append({'type': 'attribute_read_failed', 'error': str(exc)})
            return []

    def _entity_to_dict(self, obj: Any) -> dict[str, Any]:
        object_name = str(self._safe_get(obj, 'ObjectName', '') or '')
        entity_type = self._entity_type(object_name)
        item: dict[str, Any] = {
            'handle': self._safe_get(obj, 'Handle'),
            'object_name': object_name,
            'entity_type': entity_type,
            'layer': self._safe_get(obj, 'Layer'),
            'color': self._safe_get(obj, 'Color'),
            'linetype': self._safe_get(obj, 'Linetype'),
            'lineweight': self._safe_get(obj, 'Lineweight'),
            'visible': self._safe_get(obj, 'Visible'),
            'raw': {},
        }
        if entity_type == 'LINE':
            item['start'] = self._to_list(self._safe_get(obj, 'StartPoint'))
            item['end'] = self._to_list(self._safe_get(obj, 'EndPoint'))
            item['length'] = self._safe_get(obj, 'Length')
        elif entity_type == 'POLYLINE':
            coords = self._to_list(self._safe_get(obj, 'Coordinates'))
            item['coordinates'] = coords
            item['points'] = chunk_points(coords, 2)
            item['closed'] = self._safe_get(obj, 'Closed')
            item['elevation'] = self._safe_get(obj, 'Elevation')
        elif entity_type in {'TEXT', 'MTEXT'}:
            item['insert'] = self._to_list(self._safe_get(obj, 'InsertionPoint'))
            item['text'] = self._safe_get(obj, 'TextString')
            item['height'] = self._safe_get(obj, 'Height')
            item['rotation'] = self._safe_get(obj, 'Rotation')
            item['style_name'] = self._safe_get(obj, 'StyleName')
        elif entity_type == 'INSERT':
            item['name'] = self._safe_get(obj, 'Name')
            item['effective_name'] = self._safe_get(obj, 'EffectiveName')
            item['insert'] = self._to_list(self._safe_get(obj, 'InsertionPoint'))
            item['rotation'] = self._safe_get(obj, 'Rotation')
            item['x_scale'] = self._safe_get(obj, 'XScaleFactor')
            item['y_scale'] = self._safe_get(obj, 'YScaleFactor')
            item['z_scale'] = self._safe_get(obj, 'ZScaleFactor')
            item['attributes'] = self._read_attributes(obj)
        elif entity_type == 'CIRCLE':
            item['center'] = self._to_list(self._safe_get(obj, 'Center'))
            item['radius'] = self._safe_get(obj, 'Radius')
        elif entity_type == 'ARC':
            item['center'] = self._to_list(self._safe_get(obj, 'Center'))
            item['radius'] = self._safe_get(obj, 'Radius')
            item['start_angle'] = self._safe_get(obj, 'StartAngle')
            item['end_angle'] = self._safe_get(obj, 'EndAngle')
        elif entity_type == 'DIMENSION':
            item['text_override'] = self._safe_get(obj, 'TextOverride')
            item['measurement'] = self._safe_get(obj, 'Measurement')
            item['text_position'] = self._to_list(self._safe_get(obj, 'TextPosition'))
        return item

    def scan_modelspace(self) -> list[dict[str, Any]]:
        doc = self.doc or self.get_active_document()
        self.warnings.clear()
        results: list[dict[str, Any]] = []
        for obj in doc.ModelSpace:
            try:
                results.append(self._entity_to_dict(obj))
            except Exception as exc:
                warning = {'object_name': self._safe_get(obj, 'ObjectName'), 'handle': self._safe_get(obj, 'Handle'), 'error': str(exc)}
                self.warnings.append(warning)
                results.append({'object_name': 'ERROR', 'entity_type': 'ERROR', **warning})
        return results

    def _iter_modelspace(self):
        doc = self.doc or self.get_active_document()
        for obj in doc.ModelSpace:
            yield obj

    def _regen(self) -> None:
        try:
            (self.doc or self.get_active_document()).Regen(1)
        except Exception:
            pass

    def move_entity(self, handle: str, dx: float, dy: float, dz: float = 0) -> int:
        moved = 0
        for obj in self._iter_modelspace():
            if str(self._safe_get(obj, 'Handle')) == str(handle):
                obj.Move([0, 0, 0], [dx, dy, dz])
                moved += 1
        if moved:
            self._regen()
        return moved

    def move_layer(self, layer: str, dx: float, dy: float, dz: float = 0) -> int:
        moved = 0
        for obj in self._iter_modelspace():
            try:
                if str(self._safe_get(obj, 'Layer')) == layer:
                    obj.Move([0, 0, 0], [dx, dy, dz])
                    moved += 1
            except Exception:
                continue
        if moved:
            self._regen()
        return moved

    def replace_text(self, find: str, replace: str, layer: str | None = None) -> int:
        changed = 0
        for obj in self._iter_modelspace():
            object_name = str(self._safe_get(obj, 'ObjectName', '')).lower()
            if 'text' not in object_name:
                continue
            if layer and str(self._safe_get(obj, 'Layer')) != layer:
                continue
            current = self._safe_get(obj, 'TextString')
            if isinstance(current, str) and find in current:
                obj.TextString = current.replace(find, replace)
                changed += 1
        if changed:
            self._regen()
        return changed

    def delete_layer_objects(self, layer: str) -> int:
        deleted = 0
        targets = []
        for obj in self._iter_modelspace():
            if str(self._safe_get(obj, 'Layer')) == layer:
                targets.append(obj)
        for obj in targets:
            try:
                obj.Delete()
                deleted += 1
            except Exception as exc:
                self.warnings.append({'type': 'delete_failed', 'handle': self._safe_get(obj, 'Handle'), 'error': str(exc)})
        if deleted:
            self._regen()
        return deleted

    def replace_block(self, target_block: str, new_block: str, layer: str | None = None) -> dict[str, Any]:
        """Replace block references while preserving insertion, rotation and scale.

        `new_block` can be either an existing block name in the active drawing or
        a DWG file path. ZWCAD's InsertBlock accepts both in many COM profiles;
        if a specific installation requires a different method, this method will
        return per-handle errors without stopping the batch.
        """
        doc = self.doc or self.get_active_document()
        replaced = 0
        errors: list[dict[str, Any]] = []
        refs = []
        for obj in self._iter_modelspace():
            object_name = str(self._safe_get(obj, 'ObjectName', '')).lower()
            if 'block' not in object_name and 'insert' not in object_name:
                continue
            name = self._safe_get(obj, 'EffectiveName') or self._safe_get(obj, 'Name')
            if str(name).upper() != str(target_block).upper():
                continue
            if layer and str(self._safe_get(obj, 'Layer')) != layer:
                continue
            refs.append(obj)

        for obj in refs:
            try:
                insert = self._to_list(self._safe_get(obj, 'InsertionPoint')) or [0, 0, 0]
                rotation = self._safe_get(obj, 'Rotation', 0) or 0
                xs = self._safe_get(obj, 'XScaleFactor', 1) or 1
                ys = self._safe_get(obj, 'YScaleFactor', 1) or 1
                zs = self._safe_get(obj, 'ZScaleFactor', 1) or 1
                old_layer = self._safe_get(obj, 'Layer')
                new_ref = doc.ModelSpace.InsertBlock(insert, new_block, xs, ys, zs, rotation)
                try:
                    new_ref.Layer = old_layer
                except Exception:
                    pass
                obj.Delete()
                replaced += 1
            except Exception as exc:
                errors.append({'handle': self._safe_get(obj, 'Handle'), 'error': str(exc)})
        if replaced:
            self._regen()
        return {'target_block': target_block, 'new_block': new_block, 'replaced': replaced, 'errors': errors}

    def _ensure_layer(self, layer: str) -> None:
        if not layer:
            return
        doc = self.doc or self.get_active_document()
        try:
            _ = doc.Layers.Item(layer)
        except Exception:
            try:
                doc.Layers.Add(layer)
            except Exception:
                pass

    def create_line(self, start: Iterable[float], end: Iterable[float], layer: str = '0') -> Any:
        doc = self.doc or self.get_active_document()
        self._ensure_layer(layer)
        import win32com.client
        import pythoncom
        start_pt = win32com.client.VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_R8, [float(v) for v in start])
        end_pt = win32com.client.VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_R8, [float(v) for v in end])
        ent = doc.ModelSpace.AddLine(start_pt, end_pt)
        try:
            ent.Layer = layer
        except Exception:
            pass
        return ent

    def create_polyline(self, points: list[list[float]], layer: str = '0', closed: bool = True) -> Any:
        doc = self.doc or self.get_active_document()
        self._ensure_layer(layer)
        coords: list[float] = []
        for pt in points:
            coords.extend([float(pt[0]), float(pt[1])])
        import win32com.client
        import pythoncom
        coords_val = win32com.client.VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_R8, coords)
        ent = doc.ModelSpace.AddLightWeightPolyline(coords_val)
        try:
            ent.Layer = layer
        except Exception:
            pass
        try:
            ent.Closed = bool(closed)
        except Exception:
            pass
        return ent

    def insert_block(self, block_name: str, insert: Iterable[float], layer: str = '0', rotation: float = 0, scale: Iterable[float] | None = None) -> Any:
        doc = self.doc or self.get_active_document()
        self._ensure_layer(layer)
        sx, sy, sz = list(scale or [1, 1, 1])[:3]
        import win32com.client
        import pythoncom
        insert_pt = win32com.client.VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_R8, [float(v) for v in insert])
        ent = doc.ModelSpace.InsertBlock(insert_pt, block_name, sx, sy, sz, rotation)
        try:
            ent.Layer = layer
        except Exception:
            pass
        return ent

    def create_text(self, text: str, insert: Iterable[float], height: float = 150.0, layer: str = '0', color: int = 256) -> Any:
        doc = self.doc or self.get_active_document()
        self._ensure_layer(layer)
        import win32com.client
        import pythoncom
        insert_pt = win32com.client.VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_R8, [float(v) for v in insert])
        ent = doc.ModelSpace.AddText(text, insert_pt, height)
        try:
            ent.Layer = layer
        except Exception:
            pass
        try:
            if color != 256:
                ent.Color = color
        except Exception:
            pass
        return ent

    def run_command(self, command_text: str) -> None:
        if not command_text or not str(command_text).strip():
            raise ValueError('command_text is empty')
        doc = self.doc or self.get_active_document()
        text = str(command_text)
        doc.SendCommand(text if text.endswith('\n') else text + '\n')

    def load_lisp(self, path: str) -> None:
        normalized = str(Path(path)).replace('\\', '/')
        self.run_command(f'(load "{normalized}")')

    def list_layers(self) -> list[str]:
        layers: set[str] = set()
        for item in self.scan_modelspace():
            if item.get('layer'):
                layers.add(str(item['layer']))
        return sorted(layers)

    def list_blocks(self) -> list[str]:
        blocks: set[str] = set()
        for item in self.scan_modelspace():
            name = item.get('effective_name') or item.get('name')
            if name:
                blocks.add(str(name))
        return sorted(blocks)
