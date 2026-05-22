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
    """

    def __init__(self, visible: bool = True):
        self.visible = visible
        self.app: Any = None
        self.doc: Any = None
        self.warnings: list[dict[str, Any]] = []
        self.full_scan_warning_threshold = 20_000
        self.full_scan_hard_warning_threshold = 100_000

    def connect(self) -> None:
        import comtypes.client  # type: ignore
        progids = ['ZWCAD.Application.2026', 'ZWCAD.Application.2024', 'ZWCAD.Application']
        
        # 1. Try to connect to an active ZWCAD instance first
        for progid in progids:
            try:
                self.app = comtypes.client.GetActiveObject(progid)
                logger.success(f'Connected to active ZWCAD via COM: {progid}')
                return
            except Exception:
                continue
                
        # 2. If no active instance, spawn a new ZWCAD instance
        for progid in progids:
            try:
                self.app = comtypes.client.CreateObject(progid)
                self.app.Visible = self.visible
                logger.success(f'Created new ZWCAD instance via COM: {progid}')
                return
            except Exception:
                continue
                
        raise RuntimeError('Failed to connect to ZWCAD COM. GetActiveObject and CreateObject both failed for ZWCAD 2026/2024/Application.')

    def open_document(self, path: str) -> Any:
        if self.app is None:
            self.connect()
        self.doc = self.app.Documents.Open(str(Path(path)))
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
        return self._entity_to_dict_full(obj)

    def _entity_to_dict_minimal(self, obj: Any) -> dict[str, Any]:
        object_name = str(self._safe_get(obj, 'ObjectName', '') or '')
        entity_type = self._entity_type(object_name)
        return {
            'handle': self._safe_get(obj, 'Handle'),
            'object_name': object_name,
            'entity_type': entity_type,
            'layer': self._safe_get(obj, 'Layer'),
        }

    @staticmethod
    def _bbox_from_points(points: list[list[float]]) -> list[float] | None:
        clean = [p for p in points if len(p) >= 2]
        if not clean:
            return None
        xs = [float(p[0]) for p in clean]
        ys = [float(p[1]) for p in clean]
        return [min(xs), min(ys), max(xs), max(ys)]

    def _entity_to_dict_index(self, obj: Any) -> dict[str, Any]:
        item = self._entity_to_dict_minimal(obj)
        entity_type = str(item.get('entity_type') or '')
        bbox: list[float] | None = None
        if entity_type == 'LINE':
            start = self._to_list(self._safe_get(obj, 'StartPoint'))
            end = self._to_list(self._safe_get(obj, 'EndPoint'))
            bbox = self._bbox_from_points([start, end])
        elif entity_type == 'POLYLINE':
            coords = self._to_list(self._safe_get(obj, 'Coordinates'))
            bbox = self._bbox_from_points(chunk_points(coords, 2))
        elif entity_type in {'TEXT', 'MTEXT'}:
            insert = self._to_list(self._safe_get(obj, 'InsertionPoint'))
            text = self._safe_get(obj, 'TextString')
            item['insert'] = insert
            item['text'] = text[:200] if isinstance(text, str) else text
            item['height'] = self._safe_get(obj, 'Height')
            item['rotation'] = self._safe_get(obj, 'Rotation')
            bbox = self._bbox_from_points([insert])
        elif entity_type == 'INSERT':
            insert = self._to_list(self._safe_get(obj, 'InsertionPoint'))
            item['name'] = self._safe_get(obj, 'Name')
            item['effective_name'] = self._safe_get(obj, 'EffectiveName')
            item['insert'] = insert
            bbox = self._bbox_from_points([insert])
        elif entity_type == 'CIRCLE':
            center = self._to_list(self._safe_get(obj, 'Center'))
            radius = self._safe_get(obj, 'Radius')
            if center and radius is not None:
                r = float(radius)
                bbox = [float(center[0]) - r, float(center[1]) - r, float(center[0]) + r, float(center[1]) + r]
        elif entity_type == 'DIMENSION':
            item['text_override'] = self._safe_get(obj, 'TextOverride')
            item['measurement'] = self._safe_get(obj, 'Measurement')
            pos = self._to_list(self._safe_get(obj, 'TextPosition'))
            bbox = self._bbox_from_points([pos])
        item['bbox'] = bbox
        return item

    def _entity_to_dict_full(self, obj: Any) -> dict[str, Any]:
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

    def _modelspace_count(self) -> int | None:
        doc = self.doc or self.get_active_document()
        try:
            return int(doc.ModelSpace.Count)
        except Exception:
            return None

    def _scan_reader(self, mode: str):
        normalized = str(mode or 'minimal').lower()
        if normalized == 'minimal':
            return self._entity_to_dict_minimal
        if normalized == 'index':
            return self._entity_to_dict_index
        if normalized == 'full':
            return self._entity_to_dict_full
        raise ValueError(f'Unsupported scan mode: {mode}')

    def scan_modelspace(self, mode: str = 'minimal', confirm_heavy: bool = False) -> list[dict[str, Any]]:
        """Scan modelspace in minimal, index, or full mode.

        ``full`` preserves the legacy detailed JSON shape, but it is guarded on
        large drawings because every extra COM property is a cross-process call.
        """
        doc = self.doc or self.get_active_document()
        self.warnings.clear()
        normalized = str(mode or 'minimal').lower()
        count = self._modelspace_count()
        if normalized == 'full' and count is not None and count >= self.full_scan_warning_threshold and not confirm_heavy:
            self.warnings.append({
                'type': 'full_scan_blocked',
                'object_count': count,
                'threshold': self.full_scan_warning_threshold,
                'hint': 'Use mode="index" or pass confirm_heavy=True for an explicit heavy scan.',
            })
            raise RuntimeError(f'Full COM scan blocked for large drawing ({count} objects). Use confirm_heavy=True to continue.')
        if normalized == 'full' and count is not None and count >= self.full_scan_hard_warning_threshold:
            self.warnings.append({
                'type': 'full_scan_strong_warning',
                'object_count': count,
                'threshold': self.full_scan_hard_warning_threshold,
                'hint': 'Prefer native audit or DXF index for drawings this large.',
            })
        reader = self._scan_reader(normalized)
        results: list[dict[str, Any]] = []
        for obj in doc.ModelSpace:
            try:
                results.append(reader(obj))
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
        try:
            obj = self.get_entity_by_handle(handle)
            obj.Move([0, 0, 0], [dx, dy, dz])
            self._regen()
            return 1
        except Exception as exc:
            self.warnings.append({'type': 'handle_direct_access_failed', 'handle': handle, 'error': str(exc), 'fallback': 'modelspace_scan'})
        moved = 0
        for obj in self._iter_modelspace():
            if str(self._safe_get(obj, 'Handle')) == str(handle):
                obj.Move([0, 0, 0], [dx, dy, dz])
                moved += 1
        if moved:
            self._regen()
        return moved

    def get_entity_by_handle(self, handle: str) -> Any:
        if not handle:
            raise ValueError('handle is empty')
        doc = self.doc or self.get_active_document()
        try:
            return doc.HandleToObject(str(handle))
        except Exception:
            utility = self._safe_get(doc, 'Utility')
            if utility is not None:
                return utility.HandleToObject(str(handle))
            raise

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
        ent = doc.ModelSpace.AddLine(list(start), list(end))
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
        ent = doc.ModelSpace.AddLightWeightPolyline(coords)
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
        ent = doc.ModelSpace.InsertBlock(list(insert), block_name, sx, sy, sz, rotation)
        try:
            ent.Layer = layer
        except Exception:
            pass
        return ent

    def create_text(self, text: str, insert: Iterable[float], height: float = 150.0, layer: str = '0', color: int = 256) -> Any:
        doc = self.doc or self.get_active_document()
        self._ensure_layer(layer)
        ent = doc.ModelSpace.AddText(text, list(insert), height)
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
        for item in self.scan_modelspace(mode='minimal'):
            if item.get('layer'):
                layers.add(str(item['layer']))
        return sorted(layers)

    def list_blocks(self) -> list[str]:
        blocks: set[str] = set()
        for item in self.scan_modelspace(mode='index'):
            name = item.get('effective_name') or item.get('name')
            if name:
                blocks.add(str(name))
        return sorted(blocks)
