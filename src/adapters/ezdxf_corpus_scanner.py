from __future__ import annotations

from collections import Counter
from collections.abc import Iterable
from typing import Any


class EzdxfCorpusScanner:
    """Read-only ezdxf adapter that emits HS-CAD canonical entities."""

    def __init__(self, doc: Any) -> None:
        self.doc = doc
        self.warnings: list[dict[str, Any]] = []

    @staticmethod
    def _xyz(value: Any) -> list[float] | None:
        try:
            items = list(value)
            out = [float(items[0]), float(items[1])]
            out.append(float(items[2]) if len(items) > 2 else 0.0)
            return out
        except Exception:
            return None

    @staticmethod
    def _safe(entity: Any, name: str, default: Any = None) -> Any:
        try:
            return getattr(entity.dxf, name)
        except Exception:
            try:
                return getattr(entity, name)
            except Exception:
                return default

    @classmethod
    def _plain_text(cls, entity: Any) -> str | None:
        for call in (
            lambda: entity.plain_text(fast=True),
            lambda: entity.plain_text(),
            lambda: entity.plain_mtext(fast=True),
            lambda: entity.plain_mtext(),
            lambda: entity.text,
            lambda: entity.dxf.text,
        ):
            try:
                value = call()
                if isinstance(value, list):
                    value = "\n".join(str(item) for item in value)
                if value not in (None, ""):
                    return str(value)
            except Exception:
                continue
        return None

    @staticmethod
    def _bool_member(value: Any) -> bool:
        """Evaluate ezdxf boolean properties and zero-argument predicates safely."""

        try:
            return bool(value() if callable(value) else value)
        except Exception:
            return False

    def _attribute_row(self, attr: Any) -> dict[str, Any]:
        return {
            "handle": self._safe(attr, "handle"),
            "tag": self._safe(attr, "tag"),
            "text": self._plain_text(attr),
            "insert": self._xyz(self._safe(attr, "insert")),
            "layer": self._safe(attr, "layer"),
            "is_const": self._bool_member(getattr(attr, "is_const", False)),
            "is_invisible": self._bool_member(getattr(attr, "is_invisible", False)),
        }

    def _attributes(self, entity: Any) -> list[dict[str, Any]]:
        return [self._attribute_row(attr) for attr in getattr(entity, "attribs", []) or []]

    def _constant_attributes(self, entity: Any) -> list[dict[str, Any]]:
        try:
            block = entity.block()
        except Exception:
            block = None
        if block is None:
            return []
        rows: list[dict[str, Any]] = []
        for attdef in block.query("ATTDEF"):
            flags = int(self._safe(attdef, "flags", 0) or 0)
            if self._bool_member(getattr(attdef, "is_const", False)) or flags & 2:
                rows.append(self._attribute_row(attdef))
        return rows

    def _mleader_texts(self, entity: Any) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for call in (
            lambda: entity.get_mtext_content(),
            lambda: entity.context.mtext.default_content,
            lambda: entity.context.mtext.text,
        ):
            try:
                value = call()
                if value not in (None, ""):
                    out.append({"text": str(value)})
            except Exception:
                continue
        return self._deduplicate_text_rows(out)

    def _leader_annotation_texts(self, entity: Any) -> list[dict[str, Any]]:
        handle = self._safe(entity, "annotation_handle")
        if not handle:
            return []
        try:
            annotation = self.doc.entitydb.get(handle)
        except Exception:
            annotation = None
        if annotation is None:
            return []
        value = self._plain_text(annotation)
        if value in (None, ""):
            return []
        return [{"handle": self._safe(annotation, "handle"), "text": value}]

    def _dimension_text_items(self, entity: Any) -> list[dict[str, Any]]:
        try:
            block = entity.get_geometry_block()
        except Exception:
            block = None
        if block is None:
            return []
        rows: list[dict[str, Any]] = []
        try:
            text_entities = block.query("TEXT MTEXT")
        except Exception:
            text_entities = []
        for item in text_entities:
            value = self._plain_text(item)
            if value in (None, ""):
                continue
            rows.append(
                {
                    "handle": self._safe(item, "handle"),
                    "raw_text": value,
                    "source_kind": "dimension_geometry_text",
                    "insert": self._xyz(self._safe(item, "insert")),
                }
            )
        return rows

    def _table_cells(self, entity: Any) -> list[dict[str, Any]]:
        # ezdxf exposes AutoCAD tables as ACAD_TABLE and documents this helper
        # as the supported way to decode their cell matrix.
        standard_error = "unknown ACAD_TABLE decoding error"
        try:
            from ezdxf.entities.acad_table import read_acad_table_content

            content = read_acad_table_content(entity)
            return [
                {"row": row, "column": column, "text": str(value)}
                for row, values in enumerate(content)
                for column, value in enumerate(values)
                if value not in (None, "")
            ]
        except Exception as exc:
            standard_error = str(exc)

        # Retain a defensive fallback for vendor-specific table wrappers.
        out: list[dict[str, Any]] = []
        for attr in ("cells", "table_cells"):
            try:
                cells = getattr(entity, attr)
            except Exception:
                continue
            try:
                iterable = cells.items() if hasattr(cells, "items") else enumerate(cells)
                for key, cell in iterable:
                    row = column = None
                    if isinstance(key, tuple) and len(key) >= 2:
                        row, column = int(key[0]), int(key[1])
                    value = getattr(cell, "text", None) or getattr(cell, "value", None)
                    if value not in (None, ""):
                        out.append({"row": row, "column": column, "text": str(value)})
            except Exception:
                continue
        if not out:
            self.warnings.append(
                {
                    "type": "dxf_table_content_unavailable",
                    "handle": self._safe(entity, "handle"),
                    "error": standard_error,
                }
            )
        return out

    def entity_to_dict(
        self,
        entity: Any,
        *,
        layout: str,
        space: str,
        block_path: list[str] | None = None,
        source_kind: str = "drawing_entity",
    ) -> dict[str, Any]:
        etype = str(entity.dxftype()).upper()
        item: dict[str, Any] = {
            "handle": self._safe(entity, "handle"),
            "object_name": etype,
            "entity_type": etype,
            "layer": self._safe(entity, "layer"),
            "color": self._safe(entity, "color"),
            "linetype": self._safe(entity, "linetype"),
            "layout": layout,
            "space": space,
            "block_path": list(block_path or []),
            "source_kind": source_kind,
        }
        if etype == "LINE":
            item["start"] = self._xyz(self._safe(entity, "start"))
            item["end"] = self._xyz(self._safe(entity, "end"))
        elif etype in {"TEXT", "MTEXT", "ATTRIB", "ATTDEF"}:
            item["text"] = self._plain_text(entity)
            item["insert"] = self._xyz(self._safe(entity, "insert"))
            item["height"] = self._safe(entity, "height", self._safe(entity, "char_height"))
            item["rotation"] = self._safe(entity, "rotation")
            item["style_name"] = self._safe(entity, "style")
            item["tag"] = self._safe(entity, "tag")
        elif etype == "INSERT":
            item["name"] = self._safe(entity, "name")
            item["effective_name"] = self._safe(entity, "name")
            item["insert"] = self._xyz(self._safe(entity, "insert"))
            item["rotation"] = self._safe(entity, "rotation")
            item["x_scale"] = self._safe(entity, "xscale")
            item["y_scale"] = self._safe(entity, "yscale")
            item["z_scale"] = self._safe(entity, "zscale")
            item["attributes"] = self._attributes(entity)
            item["constant_attributes"] = self._constant_attributes(entity)
            # Insert.is_xref is a method in current ezdxf releases. Treating
            # the bound method itself as a bool marks every INSERT as an XREF.
            item["is_xref"] = self._bool_member(getattr(entity, "is_xref", False))
            if item["is_xref"]:
                try:
                    block = entity.block()
                except Exception:
                    block = None
                item["xref_path"] = self._xref_path(block)
        elif etype == "CIRCLE":
            item["center"] = self._xyz(self._safe(entity, "center"))
            item["radius"] = self._safe(entity, "radius")
        elif etype == "ARC":
            item["center"] = self._xyz(self._safe(entity, "center"))
            item["radius"] = self._safe(entity, "radius")
            item["start_angle"] = self._safe(entity, "start_angle")
            item["end_angle"] = self._safe(entity, "end_angle")
        elif etype in {"LWPOLYLINE", "POLYLINE"}:
            item["entity_type"] = "POLYLINE"
            try:
                if etype == "LWPOLYLINE":
                    item["points"] = [[float(x), float(y), 0.0] for x, y, *_ in entity.get_points()]
                else:
                    item["points"] = [self._xyz(vertex.dxf.location) for vertex in entity.vertices]
            except Exception:
                item["points"] = []
            item["closed"] = bool(getattr(entity, "closed", getattr(entity, "is_closed", False)))
        elif "DIMENSION" in etype:
            item["entity_type"] = "DIMENSION"
            item["text_override"] = self._safe(entity, "text")
            try:
                item["measurement"] = entity.get_measurement()
            except Exception:
                item["measurement"] = None
            item["display_text"] = (
                item.get("text_override")
                if item.get("text_override") not in (None, "", "<>")
                else item.get("measurement")
            )
            item["text_items"] = self._dimension_text_items(entity)
        elif "MLEADER" in etype:
            item["leader_texts"] = self._mleader_texts(entity)
        elif etype == "LEADER":
            item["leader_texts"] = self._leader_annotation_texts(entity)
        elif etype in {"TABLE", "ACAD_TABLE"}:
            item["table_cells"] = self._table_cells(entity)
        elif "IMAGE" in etype or "OLE" in etype:
            item["requires_ocr"] = True
            item["image_source"] = self._safe(entity, "filename", self._safe(entity, "name"))
        elif "PROXY" in etype:
            item["unsupported_proxy"] = True
        return item

    def scan(self) -> dict[str, Any]:
        self.warnings.clear()
        entities: list[dict[str, Any]] = []
        layouts: list[dict[str, Any]] = []
        entity_failure_count = 0
        missing_layout_count = 0

        for layout_name, space, layout in self._iter_layouts():
            count = 0
            try:
                iterator = iter(layout)
            except Exception as exc:
                missing_layout_count += 1
                self.warnings.append(
                    {"type": "dxf_layout_unavailable", "layout": layout_name, "error": str(exc)}
                )
                layouts.append({"name": layout_name, "space": space, "available": False})
                continue
            for entity in iterator:
                try:
                    entities.append(self.entity_to_dict(entity, layout=layout_name, space=space))
                    count += 1
                except Exception as exc:
                    entity_failure_count += 1
                    self.warnings.append(
                        {
                            "type": "dxf_entity_scan_failed",
                            "layout": layout_name,
                            "handle": self._safe(entity, "handle"),
                            "entity_type": str(entity.dxftype()),
                            "error": str(exc),
                        }
                    )
            layouts.append(
                {"name": layout_name, "space": space, "available": True, "entity_count": count}
            )

        block_entity_count = 0
        try:
            for block in self.doc.blocks:
                name = str(block.name)
                if name.startswith("*"):
                    continue
                if self._block_is_xref(block):
                    continue
                for entity in block:
                    try:
                        entities.append(
                            self.entity_to_dict(
                                entity,
                                layout="BlockDefinition",
                                space="block",
                                block_path=[name],
                                source_kind="block_definition",
                            )
                        )
                        block_entity_count += 1
                    except Exception as exc:
                        entity_failure_count += 1
                        self.warnings.append(
                            {
                                "type": "dxf_block_entity_scan_failed",
                                "block": name,
                                "handle": self._safe(entity, "handle"),
                                "error": str(exc),
                            }
                        )
        except Exception as exc:
            self.warnings.append({"type": "dxf_block_scan_failed", "error": str(exc)})

        xrefs = self._collect_xrefs(entities)
        counts = Counter(str(item.get("entity_type") or "UNKNOWN") for item in entities)
        required_ocr = sum(1 for item in entities if item.get("requires_ocr"))
        proxy_count = sum(1 for item in entities if item.get("unsupported_proxy"))
        unresolved_xrefs = sum(1 for item in xrefs if not str(item.get("path") or "").strip())
        report = {
            "schema_version": 2,
            "scanner": "ezdxf_complete",
            "entity_count": len(entities),
            "entity_type_counts": dict(sorted(counts.items())),
            "layout_count": len(layouts),
            "block_definition_entity_count": block_entity_count,
            "xref_count": len(xrefs),
            "requires_ocr_count": required_ocr,
            "unsupported_proxy_count": proxy_count,
            "unresolved_xref_count": unresolved_xrefs,
            "missing_layout_count": missing_layout_count,
            "entity_failure_count": entity_failure_count,
            "warning_count": len(self.warnings),
            "complete": not self.warnings and not required_ocr and not proxy_count and not unresolved_xrefs,
            "coverage": {
                "model_space": any(row.get("space") == "model" and row.get("available") for row in layouts),
                "paper_space": all(
                    row.get("available", False) for row in layouts if row.get("space") == "paper"
                ),
                "block_definitions": True,
                "block_attributes": True,
                "constant_attributes": True,
                "dimensions": True,
                "leaders": True,
                "tables": True,
                "xrefs_declared": True,
                "xrefs_resolved": unresolved_xrefs == 0,
                "embedded_raster_ocr": required_ocr == 0,
                "proxy_objects": proxy_count == 0,
            },
        }
        return {
            "entities": entities,
            "layouts": layouts,
            "xrefs": xrefs,
            "warnings": list(self.warnings),
            "report": report,
        }

    def _iter_layouts(self) -> Iterable[tuple[str, str, Any]]:
        yielded: set[str] = set()
        try:
            for layout in self.doc.layouts:
                name = str(layout.name)
                yielded.add(name.casefold())
                yield name, "model" if name.lower() == "model" else "paper", layout
        except Exception as exc:
            self.warnings.append(
                {"type": "dxf_layout_enumeration_failed", "error": str(exc)}
            )
            if "model" not in yielded:
                yield "Model", "model", self.doc.modelspace()

    @staticmethod
    def _deduplicate_text_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        seen: set[tuple[str, str]] = set()
        out: list[dict[str, Any]] = []
        for row in rows:
            key = (str(row.get("handle") or ""), str(row.get("text") or ""))
            if key in seen:
                continue
            seen.add(key)
            out.append(row)
        return out

    @classmethod
    def _block_is_xref(cls, block: Any) -> bool:
        try:
            return cls._bool_member(block.is_xref)
        except Exception:
            pass
        flags = cls._safe(getattr(block, "block_record", block), "flags", 0)
        try:
            return bool(int(flags or 0) & 4)
        except (TypeError, ValueError):
            return False

    @classmethod
    def _xref_path(cls, block: Any) -> str | None:
        if block is None:
            return None
        for candidate in (
            cls._safe(block, "xref_path"),
            cls._safe(getattr(block, "block_record", block), "xref_path"),
            cls._safe(getattr(block, "block", block), "xref_path"),
        ):
            if candidate not in (None, ""):
                return str(candidate)
        return None

    @staticmethod
    def _collect_xrefs(entities: list[dict[str, Any]]) -> list[dict[str, Any]]:
        rows: dict[tuple[str, str], dict[str, Any]] = {}
        for item in entities:
            if not item.get("is_xref"):
                continue
            name = str(item.get("name") or "")
            path = str(item.get("xref_path") or "")
            rows[(name, path)] = {
                "name": name,
                "path": path or None,
                "handle": item.get("handle"),
                "loaded": bool(path),
                "layout": item.get("layout"),
            }
        return list(rows.values())
