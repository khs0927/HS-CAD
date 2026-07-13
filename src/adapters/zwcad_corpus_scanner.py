from __future__ import annotations

from collections import Counter
from typing import Any, Iterable

from src.adapters.zwcad_com_adapter import ZWCADCOMAdapter


class ZWCADCorpusScanner:
    """Read-only scanner for layouts, blocks and every searchable CAD text source."""

    def __init__(self, adapter: ZWCADCOMAdapter):
        self.adapter = adapter
        self.warnings: list[dict[str, Any]] = []
        self._seen: set[tuple[str, str, str]] = set()

    @staticmethod
    def _safe_get(obj: Any, name: str, default: Any = None) -> Any:
        try:
            value = getattr(obj, name)
            return list(value) if isinstance(value, tuple) else value
        except Exception:
            return default

    @staticmethod
    def _iter_collection(value: Any) -> Iterable[Any]:
        if value is None:
            return ()
        try:
            return iter(value)
        except Exception:
            items: list[Any] = []
            try:
                count = int(value.Count)
            except Exception:
                return ()
            for index in range(count):
                for candidate in (index, index + 1):
                    try:
                        items.append(value.Item(candidate))
                        break
                    except Exception:
                        continue
            return iter(items)

    def _attribute_rows(self, obj: Any, method_name: str) -> list[dict[str, Any]]:
        try:
            attrs = getattr(obj, method_name)()
        except Exception:
            return []
        rows: list[dict[str, Any]] = []
        for attr in self._iter_collection(attrs):
            rows.append(
                {
                    "handle": self._safe_get(attr, "Handle"),
                    "tag": self._safe_get(attr, "TagString"),
                    "text": self._safe_get(attr, "TextString"),
                    "insert": self._safe_get(attr, "InsertionPoint"),
                    "layer": self._safe_get(attr, "Layer"),
                }
            )
        return rows

    def _table_cells(self, obj: Any) -> list[dict[str, Any]]:
        try:
            row_count = int(self._safe_get(obj, "Rows"))
            column_count = int(self._safe_get(obj, "Columns"))
        except (TypeError, ValueError):
            return []
        if row_count < 0 or column_count < 0 or row_count * column_count > 100_000:
            self.warnings.append(
                {
                    "type": "table_size_rejected",
                    "handle": self._safe_get(obj, "Handle"),
                    "rows": row_count,
                    "columns": column_count,
                }
            )
            return []
        out: list[dict[str, Any]] = []
        for row in range(row_count):
            for column in range(column_count):
                value = None
                for method_name in ("GetText", "GetCellValue", "GetValue"):
                    try:
                        value = getattr(obj, method_name)(row, column)
                        if value is not None:
                            break
                    except Exception:
                        continue
                if value not in (None, ""):
                    out.append({"row": row, "column": column, "text": str(value)})
        return out

    def _leader_texts(self, obj: Any) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for attr in ("TextString", "TextContent", "Contents"):
            value = self._safe_get(obj, attr)
            if value not in (None, ""):
                out.append({"text": str(value)})
        mtext = self._safe_get(obj, "MText")
        if mtext is not None:
            value = self._safe_get(mtext, "TextString")
            if value not in (None, ""):
                out.append(
                    {"handle": self._safe_get(mtext, "Handle"), "text": str(value)}
                )
        return out

    def _dimension_display(self, obj: Any) -> str | None:
        for attr in ("TextString", "DimensionText", "TextOverride"):
            value = self._safe_get(obj, attr)
            if value not in (None, "", "<>"):
                return str(value)
        measurement = self._safe_get(obj, "Measurement")
        return None if measurement is None else str(measurement)

    def _enrich_entity(
        self,
        obj: Any,
        *,
        layout: str,
        space: str,
        block_path: list[str] | None = None,
        source_kind: str = "drawing_entity",
    ) -> dict[str, Any]:
        item = self.adapter._entity_to_dict(obj)
        item.update(
            {
                "layout": layout,
                "space": space,
                "block_path": list(block_path or []),
                "source_kind": source_kind,
                "owner_handle": self._safe_get(obj, "OwnerID"),
            }
        )
        upper = str(item.get("object_name") or "").upper()
        if "BLOCKREFERENCE" in upper or item.get("entity_type") == "INSERT":
            item["attributes"] = self._attribute_rows(obj, "GetAttributes")
            item["constant_attributes"] = self._attribute_rows(
                obj, "GetConstantAttributes"
            )
        if "TABLE" in upper:
            item["table_cells"] = self._table_cells(obj)
        if "MLEADER" in upper or upper.endswith("LEADER"):
            item["leader_texts"] = self._leader_texts(obj)
        if "DIMENSION" in upper or item.get("entity_type") == "DIMENSION":
            item["display_text"] = self._dimension_display(obj)
            item["text_string"] = self._safe_get(obj, "TextString")
        if "OLE" in upper or "RASTERIMAGE" in upper or "IMAGE" in upper:
            item["requires_ocr"] = True
            item["image_source"] = (
                self._safe_get(obj, "ImageFile")
                or self._safe_get(obj, "SourceFileName")
                or self._safe_get(obj, "Name")
            )
        return item

    def _append_entity(
        self,
        out: list[dict[str, Any]],
        obj: Any,
        *,
        layout: str,
        space: str,
        block_path: list[str] | None = None,
        source_kind: str = "drawing_entity",
    ) -> None:
        handle = str(self._safe_get(obj, "Handle") or "")
        key = (handle, layout, "/".join(block_path or []))
        if handle and key in self._seen:
            return
        if handle:
            self._seen.add(key)
        try:
            out.append(
                self._enrich_entity(
                    obj,
                    layout=layout,
                    space=space,
                    block_path=block_path,
                    source_kind=source_kind,
                )
            )
        except Exception as exc:
            self.warnings.append(
                {
                    "type": "entity_scan_failed",
                    "handle": handle or None,
                    "layout": layout,
                    "block_path": list(block_path or []),
                    "object_name": self._safe_get(obj, "ObjectName"),
                    "error": str(exc),
                }
            )

    def _scan_space(self, collection: Any, *, layout: str, space: str) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for obj in self._iter_collection(collection):
            self._append_entity(out, obj, layout=layout, space=space)
        return out

    def _scan_layouts(self, doc: Any) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        entities: list[dict[str, Any]] = []
        layouts: list[dict[str, Any]] = []
        scanned_model = False
        for layout_obj in self._iter_collection(self._safe_get(doc, "Layouts")):
            name = str(self._safe_get(layout_obj, "Name") or "Layout")
            model_type = bool(
                self._safe_get(layout_obj, "ModelType", name.lower() == "model")
            )
            block = self._safe_get(layout_obj, "Block")
            space = "model" if model_type else "paper"
            if block is None:
                block = self._safe_get(
                    doc, "ModelSpace" if model_type else "PaperSpace"
                )
            if block is None:
                self.warnings.append(
                    {"type": "layout_collection_unavailable", "layout": name}
                )
                continue
            entities.extend(self._scan_space(block, layout=name, space=space))
            scanned_model = scanned_model or model_type
            layouts.append(
                {
                    "name": name,
                    "space": space,
                    "tab_order": self._safe_get(layout_obj, "TabOrder"),
                    "block_handle": self._safe_get(block, "Handle"),
                }
            )
        if not scanned_model:
            model = self._safe_get(doc, "ModelSpace")
            if model is not None:
                entities.extend(self._scan_space(model, layout="Model", space="model"))
                layouts.append({"name": "Model", "space": "model"})
        return entities, layouts

    def _scan_block_definitions(self, doc: Any) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        entities: list[dict[str, Any]] = []
        xrefs: list[dict[str, Any]] = []
        for block in self._iter_collection(self._safe_get(doc, "Blocks")):
            name = str(self._safe_get(block, "Name") or "")
            if not name:
                continue
            is_layout = bool(self._safe_get(block, "IsLayout", False))
            is_xref = bool(self._safe_get(block, "IsXRef", False))
            path = (
                self._safe_get(block, "Path")
                or self._safe_get(block, "XRefPath")
                or self._safe_get(block, "Name")
            )
            if is_xref:
                xrefs.append(
                    {
                        "name": name,
                        "path": None if path is None else str(path),
                        "handle": self._safe_get(block, "Handle"),
                        "loaded": not bool(self._safe_get(block, "IsUnloaded", False)),
                    }
                )
                continue
            if is_layout or name.startswith("*"):
                continue
            for obj in self._iter_collection(block):
                self._append_entity(
                    entities,
                    obj,
                    layout="BlockDefinition",
                    space="block",
                    block_path=[name],
                    source_kind="block_definition",
                )
        return entities, xrefs

    def scan_document(self) -> dict[str, Any]:
        doc = self.adapter.doc or self.adapter.get_active_document()
        self.warnings.clear()
        self._seen.clear()
        entities, layouts = self._scan_layouts(doc)
        block_entities, xrefs = self._scan_block_definitions(doc)
        entities.extend(block_entities)
        counts = Counter(str(item.get("entity_type") or "UNKNOWN") for item in entities)
        required_ocr = sum(1 for item in entities if item.get("requires_ocr"))
        report = {
            "schema_version": 2,
            "scanner": "zwcad_com_complete",
            "entity_count": len(entities),
            "entity_type_counts": dict(sorted(counts.items())),
            "layout_count": len(layouts),
            "block_definition_entity_count": len(block_entities),
            "xref_count": len(xrefs),
            "requires_ocr_count": required_ocr,
            "warning_count": len(self.warnings),
            "coverage": {
                "model_space": any(row.get("space") == "model" for row in layouts),
                "paper_space": any(row.get("space") == "paper" for row in layouts),
                "block_definitions": True,
                "block_attributes": True,
                "constant_attributes": True,
                "dimensions": True,
                "leaders": True,
                "tables": True,
                "xrefs_declared": True,
                "embedded_raster_ocr": required_ocr == 0,
            },
        }
        return {
            "entities": entities,
            "layouts": layouts,
            "xrefs": xrefs,
            "report": report,
            "warnings": list(self.warnings),
        }
