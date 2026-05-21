from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable

from src.app import logger
from src.cad_core.base import CADAdapter
from src.cad_core.drawing_standards import (
    CADGenerationStandards,
    cad_unicode_escape,
    insulation_batting_pattern_points,
    insulation_centerline,
    measured_dimension_override,
    qleader_l_route_points,
    resolve_annotation_style,
    text_box_width,
)
from src.semantics.layer_taxonomy import canonical_layer_name, get_layer_rule, normalize_layer_name
from src.testing.environment_check import zwcad_progid_candidates
from src.utils.geometry import chunk_points


class ZWCADCOMAdapter(CADAdapter):
    """ZWCAD COM/ActiveX adapter.

    The adapter is intentionally defensive: all Windows-only modules are imported
    lazily, every COM attribute access is guarded, and a single bad entity never
    stops a drawing scan. This keeps `--help` and pytest usable on non-ZWCAD
    machines while still providing an executable fallback on Windows.
    """

    def __init__(self, visible: bool = True, version: str | None = None, start_if_needed: bool = True):
        self.visible = visible
        self.version = version
        self.start_if_needed = start_if_needed
        self.active_progid: str | None = None
        self.connection_attempts: list[dict[str, Any]] = []
        self.app: Any = None
        self.doc: Any = None
        self.warnings: list[dict[str, Any]] = []
        self.standards = CADGenerationStandards()

    def connect(self) -> None:
        errors: list[str] = []
        candidates = zwcad_progid_candidates(self.version)
        for progid in candidates:
            for mode in (["active", "create"] if self.start_if_needed else ["active"]):
                try:
                    if mode == "active":
                        try:
                            import win32com.client  # type: ignore
                            app = win32com.client.GetActiveObject(progid)
                        except Exception:
                            import comtypes.client  # type: ignore
                            app = comtypes.client.GetActiveObject(progid)
                    else:
                        try:
                            import win32com.client  # type: ignore
                            app = win32com.client.Dispatch(progid)
                        except Exception:
                            import comtypes.client  # type: ignore
                            app = comtypes.client.CreateObject(progid)
                    self.app = app
                    self.active_progid = progid
                    try:
                        self.app.Visible = self.visible
                    except Exception:
                        pass
                    self.connection_attempts.append({'progid': progid, 'mode': mode, 'ok': True})
                    logger.success(f'Connected to ZWCAD via COM: {progid} ({mode})')
                    return
                except Exception as exc:
                    message = f'{progid}/{mode}: {exc}'
                    errors.append(message)
                    self.connection_attempts.append({'progid': progid, 'mode': mode, 'ok': False, 'error': str(exc)})
        raise RuntimeError('Failed to connect to ZWCAD COM. Tried ' + ', '.join(candidates) + '. Errors: ' + ' | '.join(errors[-6:]))

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

    safe_get = _safe_get

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
        try:
            obj = (self.doc or self.get_active_document()).HandleToObject(str(handle))
            obj.Move([0, 0, 0], [dx, dy, dz])
            self._regen()
            return 1
        except Exception:
            pass
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

    def delete_layer_objects(self, layer: str, yes: bool = False, dry_run: bool = False) -> int:
        if not str(layer or "").strip():
            raise ValueError("layer is required")
        if str(layer).strip().lower() in {"0", "defpoints"}:
            raise PermissionError(f"Refusing to delete protected layer: {layer}")
        deleted = 0
        targets = []
        for obj in self._iter_modelspace():
            if str(self._safe_get(obj, 'Layer')) == layer:
                targets.append(obj)
        if dry_run:
            return len(targets)
        if not yes:
            raise PermissionError("delete_layer_objects requires yes=True when dry_run=False")
        for obj in targets:
            try:
                obj.Delete()
                deleted += 1
            except Exception as exc:
                self.warnings.append({'type': 'delete_failed', 'handle': self._safe_get(obj, 'Handle'), 'error': str(exc)})
        if deleted:
            self._regen()
        return deleted

    def consolidate_other_layers(
        self,
        target_layer: str = "ETC",
        keep_layers: Iterable[str] | None = None,
        dry_run: bool = True,
    ) -> dict[str, Any]:
        """Move objects on non-standard layers into one target layer.

        Standard/user-defined layers are preserved using the layer taxonomy.
        Additional keep layers can be supplied for project-specific exceptions.
        """
        target = str(target_layer or "").strip()
        if not target:
            raise ValueError("target_layer is required")

        keep = {normalize_layer_name(layer) for layer in (keep_layers or [])}
        keep.update({"0", "DEFPOINTS", normalize_layer_name(target)})
        plan: dict[str, Any] = {
            "target_layer": target,
            "dry_run": dry_run,
            "changed": 0,
            "mapped_layers": {},
            "source_layers": {},
            "review_layers": {},
            "preserved_layers": {},
            "errors": [],
        }
        targets: list[tuple[Any, str]] = []
        for obj in self._iter_modelspace():
            layer = str(self._safe_get(obj, "Layer", "") or "").strip()
            normalized = normalize_layer_name(layer)
            if not layer:
                plan["preserved_layers"]["<NO_LAYER>"] = plan["preserved_layers"].get("<NO_LAYER>", 0) + 1
                continue
            canonical = canonical_layer_name(layer)
            if normalized in keep:
                plan["preserved_layers"][layer] = plan["preserved_layers"].get(layer, 0) + 1
                continue
            if canonical and normalize_layer_name(canonical) != normalized:
                key = f"{layer} -> {canonical}"
                plan["mapped_layers"][key] = plan["mapped_layers"].get(key, 0) + 1
                targets.append((obj, canonical))
                continue
            if canonical or get_layer_rule(layer) is not None:
                plan["preserved_layers"][layer] = plan["preserved_layers"].get(layer, 0) + 1
                continue
            plan["source_layers"][layer] = plan["source_layers"].get(layer, 0) + 1
            plan["review_layers"][layer] = plan["review_layers"].get(layer, 0) + 1
            targets.append((obj, target))

        if dry_run:
            plan["changed"] = len(targets)
            return plan

        changed = 0
        for obj, destination_layer in targets:
            try:
                self._ensure_layer(destination_layer)
                obj.Layer = destination_layer
                changed += 1
            except Exception as exc:
                plan["errors"].append({"handle": self._safe_get(obj, "Handle"), "error": str(exc)})
        plan["changed"] = changed
        if changed:
            self._regen()
        return plan

    def _block_exists(self, block_name: str) -> bool:
        doc = self.doc or self.get_active_document()
        try:
            for block in doc.Blocks:
                if str(self._safe_get(block, "Name", "")).upper() == str(block_name).upper():
                    return True
        except Exception:
            pass
        return Path(str(block_name)).exists()

    def replace_block(
        self,
        target_block: str,
        new_block: str,
        layer: str | None = None,
        preserve_rotation: bool = True,
        preserve_scale: bool = True,
        preserve_layer: bool = True,
        delete_original: bool = True,
    ) -> dict[str, Any]:
        """Replace block references while preserving insertion, rotation and scale.

        `new_block` can be either an existing block name in the active drawing or
        a DWG file path. ZWCAD's InsertBlock accepts both in many COM profiles;
        if a specific installation requires a different method, this method will
        return per-handle errors without stopping the batch.
        """
        doc = self.doc or self.get_active_document()
        if not self._block_exists(new_block):
            return {'target_block': target_block, 'new_block': new_block, 'replaced': 0, 'errors': [{'error': 'new block definition missing'}]}
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
                rotation = (self._safe_get(obj, 'Rotation', 0) or 0) if preserve_rotation else 0
                xs = (self._safe_get(obj, 'XScaleFactor', 1) or 1) if preserve_scale else 1
                ys = (self._safe_get(obj, 'YScaleFactor', 1) or 1) if preserve_scale else 1
                zs = (self._safe_get(obj, 'ZScaleFactor', 1) or 1) if preserve_scale else 1
                old_layer = self._safe_get(obj, 'Layer') if preserve_layer else (layer or self._safe_get(obj, 'Layer'))
                new_ref = doc.ModelSpace.InsertBlock(insert, new_block, xs, ys, zs, rotation)
                try:
                    new_ref.Layer = old_layer
                except Exception:
                    pass
                if delete_original:
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

    def _variant_point(self, point: Iterable[float]) -> Any:
        values = [float(v) for v in point]
        while len(values) < 3:
            values.append(0.0)
        try:
            import pythoncom  # type: ignore
            import win32com.client  # type: ignore

            return win32com.client.VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_R8, values[:3])
        except Exception:
            return values[:3]

    def _variant_array(self, values: Iterable[float]) -> Any:
        vals = [float(v) for v in values]
        try:
            import pythoncom  # type: ignore
            import win32com.client  # type: ignore

            return win32com.client.VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_R8, vals)
        except Exception:
            return vals

    def list_dim_styles(self) -> list[str]:
        doc = self.doc or self.get_active_document()
        styles: set[str] = set()
        try:
            for style in doc.DimStyles:
                name = str(self._safe_get(style, "Name", ""))
                if name:
                    styles.add(name)
        except Exception:
            pass
        return sorted(styles)

    def resolve_annotation_style(self, requested_style: str | None = None) -> str:
        return resolve_annotation_style(
            self.list_dim_styles(),
            requested_style=requested_style,
            preferred_style=self.standards.preferred_annotation_style,
            fallback_style=self.standards.annotation_style,
        )

    def apply_annotation_style(self, entity: Any, style: str | None = None) -> Any:
        resolved = self.resolve_annotation_style(style)
        try:
            entity.StyleName = resolved
        except Exception as exc:
            self.warnings.append({"type": "style_apply_failed", "style": resolved, "error": str(exc)})
        return entity

    def ensure_linetype(self, linetype: str | None = None, search_paths: Iterable[str] | None = None) -> bool:
        doc = self.doc or self.get_active_document()
        target = linetype or self.standards.batting_linetype
        try:
            _ = doc.Linetypes.Item(target)
            return True
        except Exception:
            pass
        for path in search_paths or self.standards.linetype_search_paths:
            if not Path(path).exists():
                continue
            try:
                doc.Linetypes.Load(target, str(path))
                return True
            except Exception as exc:
                self.warnings.append({"type": "linetype_load_failed", "linetype": target, "path": str(path), "error": str(exc)})
        return False

    def auto_correct_scales(self, batting_width_mm: float | None = None, model_ltscale: float | None = None) -> dict[str, Any]:
        """Normalize drawing scale settings used by generated detail geometry."""

        doc = self.doc or self.get_active_document()
        applied: dict[str, Any] = {}
        ltscale = self.standards.model_ltscale if model_ltscale is None else float(model_ltscale)
        try:
            doc.SetVariable("LTSCALE", ltscale)
            applied["LTSCALE"] = ltscale
        except Exception as exc:
            self.warnings.append({"type": "ltscale_apply_failed", "error": str(exc)})
        batting_scale = self.standards.batting_scale_for_width(batting_width_mm)
        for obj in self._iter_modelspace():
            try:
                if str(self._safe_get(obj, "Linetype", "")).upper() == self.standards.batting_linetype.upper():
                    obj.LinetypeScale = batting_scale
            except Exception:
                continue
        applied["BATTING_LINETYPE_SCALE"] = batting_scale
        return applied

    def configure_drawing_standards(
        self,
        annotation_style: str | None = None,
        batting_width_mm: float | None = None,
        load_batting: bool = True,
    ) -> dict[str, Any]:
        """Apply default or user-requested drafting standards before generation."""

        resolved_style = self.resolve_annotation_style(annotation_style)
        if load_batting:
            self.ensure_linetype(self.standards.batting_linetype)
        scales = self.auto_correct_scales(batting_width_mm=batting_width_mm)
        return {"annotation_style": resolved_style, "scales": scales}

    def create_line(self, start: Iterable[float], end: Iterable[float], layer: str = '0') -> Any:
        doc = self.doc or self.get_active_document()
        self._ensure_layer(layer)
        ent = doc.ModelSpace.AddLine(self._variant_point(start), self._variant_point(end))
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
        ent = doc.ModelSpace.AddLightWeightPolyline(self._variant_array(coords))
        try:
            ent.Layer = layer
        except Exception:
            pass
        try:
            ent.Closed = bool(closed)
        except Exception:
            pass
        return ent

    def create_circle(self, center: Iterable[float], radius: float, layer: str = '0') -> Any:
        doc = self.doc or self.get_active_document()
        self._ensure_layer(layer)
        ent = doc.ModelSpace.AddCircle(self._variant_point(center), float(radius))
        try:
            ent.Layer = layer
        except Exception:
            pass
        return ent

    def insert_block(self, block_name: str, insert: Iterable[float], layer: str = '0', rotation: float = 0, scale: Iterable[float] | None = None) -> Any:
        doc = self.doc or self.get_active_document()
        self._ensure_layer(layer)
        sx, sy, sz = list(scale or [1, 1, 1])[:3]
        ent = doc.ModelSpace.InsertBlock(self._variant_point(insert), block_name, sx, sy, sz, rotation)
        try:
            ent.Layer = layer
        except Exception:
            pass
        return ent

    def create_text(
        self,
        text: str,
        insert: Iterable[float],
        height: float | None = None,
        layer: str = "0",
        rotation: float = 0,
        unicode_escape: bool = True,
    ) -> Any:
        doc = self.doc or self.get_active_document()
        self._ensure_layer(layer)
        value = cad_unicode_escape(text) if unicode_escape else str(text)
        ent = doc.ModelSpace.AddText(value, self._variant_point(insert), float(height or self.standards.default_text_height))
        try:
            ent.Layer = layer
            ent.Rotation = float(rotation)
        except Exception:
            pass
        return ent

    def create_aligned_dimension(
        self,
        start: Iterable[float],
        end: Iterable[float],
        text_position: Iterable[float],
        text_override: str | None = None,
        layer: str | None = None,
        style: str | None = None,
    ) -> Any:
        doc = self.doc or self.get_active_document()
        target_layer = layer or self.standards.dimension_layer
        self._ensure_layer(target_layer)
        ent = doc.ModelSpace.AddDimAligned(self._variant_point(start), self._variant_point(end), self._variant_point(text_position))
        try:
            ent.Layer = target_layer
            ent.TextOverride = measured_dimension_override()
            ent.ScaleFactor = self.standards.default_dimension_scale
            if text_override:
                self.warnings.append({
                    "type": "dimension_text_override_ignored",
                    "requested": str(text_override),
                    "reason": "generated dimensions must display measured geometry",
                })
        except Exception:
            pass
        return self.apply_annotation_style(ent, style)

    def create_qleader_label(
        self,
        target: Iterable[float],
        label_origin: Iterable[float],
        label: str,
        text_height: float | None = None,
        layer: str | None = None,
        text_layer: str | None = None,
        style: str | None = None,
    ) -> dict[str, Any]:
        height = float(text_height or self.standards.default_text_height)
        origin = list(label_origin)
        target_values = list(target)
        label_width = text_box_width(label, height)
        route2d = qleader_l_route_points(
            (float(target_values[0]), float(target_values[1])),
            (float(origin[0]), float(origin[1])),
            label_width,
            height,
        )
        z = float(target_values[2]) if len(target_values) > 2 else 0.0
        leader = self.create_orthogonal_leader(
            [[x, y, z] for x, y in route2d],
            layer=layer,
            style=style,
        )
        text_entity = self.create_text(
            label,
            [float(origin[0]), float(origin[1]), float(origin[2]) if len(origin) > 2 else z],
            height=height,
            layer=text_layer or "DET_TEXT",
        )
        return {"leader": leader, "text": text_entity, "points": route2d}

    def create_orthogonal_leader(
        self,
        points: list[Iterable[float]],
        layer: str | None = None,
        style: str | None = None,
    ) -> Any:
        if len(points) < 3:
            raise ValueError("orthogonal leader requires at least target, elbow and landing points")
        doc = self.doc or self.get_active_document()
        target_layer = layer or self.standards.leader_layer
        self._ensure_layer(target_layer)
        flat: list[float] = []
        for point in points:
            values = [float(v) for v in point]
            while len(values) < 3:
                values.append(0.0)
            flat.extend(values[:3])
        ent = doc.ModelSpace.AddLeader(self._variant_array(flat), None, 0)
        try:
            ent.Layer = target_layer
        except Exception:
            pass
        return self.apply_annotation_style(ent, style)

    def create_insulation_batting_pattern(
        self,
        origin: Iterable[float],
        thickness_mm: float,
        length_mm: float,
        vertical: bool = True,
        layer: str | None = None,
    ) -> dict[str, Any]:
        values = list(origin)
        xy = (float(values[0]), float(values[1]))
        z = float(values[2]) if len(values) > 2 else 0.0
        target_layer = layer or self.standards.insulation_layer
        points = insulation_batting_pattern_points(xy, thickness_mm, length_mm, vertical=vertical)
        polyline = self.create_polyline([[x, y, z] for x, y in points], target_layer, closed=False) if points else None
        start, end = insulation_centerline(xy, thickness_mm, length_mm, vertical=vertical)
        centerline = self.create_line([start[0], start[1], z], [end[0], end[1], z], target_layer)
        return {"pattern": polyline, "centerline": centerline, "points": points}

    def apply_batting_linetype(self, entity: Any, width_mm: float | None = None) -> Any:
        self.ensure_linetype(self.standards.batting_linetype)
        try:
            entity.Linetype = self.standards.batting_linetype
            entity.LinetypeScale = self.standards.batting_scale_for_width(width_mm)
        except Exception as exc:
            self.warnings.append({"type": "batting_apply_failed", "error": str(exc)})
        return entity

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
        doc = self.doc or self.get_active_document()
        layers: set[str] = set()
        try:
            for layer in doc.Layers:
                layers.add(str(self._safe_get(layer, "Name", "")))
        except Exception:
            # Fallback if collection iteration fails
            for item in self.scan_modelspace():
                if item.get("layer"):
                    layers.add(str(item["layer"]))
        return sorted([L for L in layers if L])

    def list_blocks(self) -> list[str]:
        doc = self.doc or self.get_active_document()
        blocks: set[str] = set()
        try:
            for block in doc.Blocks:
                name = str(self._safe_get(block, "Name", ""))
                if name and not name.startswith("*"):  # Skip anonymous blocks
                    blocks.add(name)
        except Exception:
            # Fallback if collection iteration fails
            for item in self.scan_modelspace():
                name = item.get("effective_name") or item.get("name")
                if name:
                    blocks.add(str(name))
        return sorted(list(blocks))
