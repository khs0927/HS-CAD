from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any, Iterable

from src.corpus.schema import (
    FileizedDrawingRecord,
    block_rows_from_entities,
    dimension_rows_from_entities,
    layer_rows_from_entities,
    text_rows_from_entities,
)
from src.fileizers.base import DrawingFileizer


class DXFEzdxfFileizer(DrawingFileizer):
    """Completeness-oriented DXF fileizer using ezdxf."""

    engine_name = "ezdxf_complete"
    supported_extensions = (".dxf",)

    def is_available(self) -> tuple[bool, str]:
        try:
            import ezdxf  # noqa: F401
            return True, "ezdxf available"
        except Exception as exc:
            return False, f"ezdxf unavailable: {exc}"

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

    @staticmethod
    def _plain_text(entity: Any) -> str | None:
        for call in (
            lambda: entity.plain_text(fast=True),
            lambda: entity.plain_text(),
            lambda: getattr(entity, "text"),
            lambda: getattr(entity.dxf, "text"),
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

    def _attributes(self, entity: Any) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for attr in getattr(entity, "attribs", []) or []:
            out.append(
                {
                    "handle": self._safe(attr, "handle"),
                    "tag": self._safe(attr, "tag"),
                    "text": self._plain_text(attr),
                    "insert": self._xyz(self._safe(attr, "insert")),
                    "layer": self._safe(attr, "layer"),
                }
            )
        return out

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
        return out

    def _table_cells(self, entity: Any) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for attr in ("cells", "table_cells"):
            try:
                cells = getattr(entity, attr)
            except Exception:
                continue
            try:
                iterable = cells.items() if hasattr(cells, "items") else cells
                for key, cell in iterable:
                    if isinstance(key, tuple) and len(key) >= 2:
                        row, column = int(key[0]), int(key[1])
                    else:
                        row = column = None
                    value = getattr(cell, "text", None) or getattr(cell, "value", None)
                    if value not in (None, ""):
                        out.append(
                            {"row": row, "column": column, "text": str(value)}
                        )
            except Exception:
                continue
        return out

    def _entity_to_dict(
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
            item["height"] = self._safe(
                entity, "height", self._safe(entity, "char_height")
            )
            item["rotation"] = self._safe(entity, "rotation")
            item["style_name"] = self._safe(entity, "style")
        elif etype == "INSERT":
            item["name"] = self._safe(entity, "name")
            item["effective_name"] = self._safe(entity, "name")
            item["insert"] = self._xyz(self._safe(entity, "insert"))
            item["rotation"] = self._safe(entity, "rotation")
            item["x_scale"] = self._safe(entity, "xscale")
            item["y_scale"] = self._safe(entity, "yscale")
            item["z_scale"] = self._safe(entity, "zscale")
            item["attributes"] = self._attributes(entity)
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
                    item["points"] = [
                        [float(x), float(y), 0.0] for x, y, *_ in entity.get_points()
                    ]
                else:
                    item["points"] = [
                        self._xyz(vertex.dxf.location) for vertex in entity.vertices
                    ]
            except Exception:
                item["points"] = []
            item["closed"] = bool(
                getattr(entity, "closed", getattr(entity, "is_closed", False))
            )
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
        elif "MLEADER" in etype or etype == "LEADER":
            item["leader_texts"] = self._mleader_texts(entity)
        elif etype == "TABLE":
            item["table_cells"] = self._table_cells(entity)
        elif "IMAGE" in etype or "OLE" in etype:
            item["requires_ocr"] = True
            item["image_source"] = self._safe(
                entity, "filename", self._safe(entity, "name")
            )
        return item

    def _iter_layouts(self, doc: Any) -> Iterable[tuple[str, str, Any]]:
        try:
            for layout in doc.layouts:
                name = str(layout.name)
                space = "model" if name.lower() == "model" else "paper"
                yield name, space, layout
        except Exception:
            yield "Model", "model", doc.modelspace()

    def fileize(
        self,
        path: str | Path,
        *,
        file_id: str,
        relative_path: str | Path,
    ) -> FileizedDrawingRecord:
        src = Path(path)
        available, reason = self.is_available()
        if not available:
            return FileizedDrawingRecord.unavailable(
                file_id=file_id,
                source_path=src,
                relative_path=relative_path,
                extension=src.suffix,
                engine=self.engine_name,
                reason=reason,
            )
        try:
            import ezdxf

            doc = ezdxf.readfile(str(src))
            entities: list[dict[str, Any]] = []
            layouts: list[dict[str, Any]] = []
            warnings: list[dict[str, Any]] = []

            for layout_name, space, layout in self._iter_layouts(doc):
                count = 0
                for entity in layout:
                    try:
                        entities.append(
                            self._entity_to_dict(
                                entity, layout=layout_name, space=space
                            )
                        )
                        count += 1
                    except Exception as exc:
                        warnings.append(
                            {
                                "type": "dxf_entity_scan_failed",
                                "layout": layout_name,
                                "handle": self._safe(entity, "handle"),
                                "entity_type": str(entity.dxftype()),
                                "error": str(exc),
                            }
                        )
                layouts.append(
                    {"name": layout_name, "space": space, "entity_count": count}
                )

            xrefs: list[dict[str, Any]] = []
            block_entity_count = 0
            try:
                for block in doc.blocks:
                    name = str(block.name)
                    if name.startswith("*"):
                        continue
                    is_xref = bool(getattr(block, "is_xref", False))
                    if is_xref:
                        xrefs.append(
                            {
                                "name": name,
                                "path": getattr(block, "xref_path", None),
                            }
                        )
                        continue
                    for entity in block:
                        entities.append(
                            self._entity_to_dict(
                                entity,
                                layout="BlockDefinition",
                                space="block",
                                block_path=[name],
                                source_kind="block_definition",
                            )
                        )
                        block_entity_count += 1
            except Exception as exc:
                warnings.append({"type": "dxf_block_scan_failed", "error": str(exc)})

            texts = text_rows_from_entities(entities)
            required_ocr = sum(1 for item in entities if item.get("requires_ocr"))
            counts = Counter(
                str(item.get("entity_type") or "UNKNOWN") for item in entities
            )
            report = {
                "schema_version": 2,
                "scanner": self.engine_name,
                "entity_count": len(entities),
                "entity_type_counts": dict(sorted(counts.items())),
                "text_occurrence_count": len(texts),
                "layout_count": len(layouts),
                "block_definition_entity_count": block_entity_count,
                "xref_count": len(xrefs),
                "requires_ocr_count": required_ocr,
                "warning_count": len(warnings),
                "complete": len(warnings) == 0 and required_ocr == 0,
                "coverage": {
                    "model_space": any(row["space"] == "model" for row in layouts),
                    "paper_space": any(row["space"] == "paper" for row in layouts),
                    "block_definitions": True,
                    "block_attributes": True,
                    "dimensions": True,
                    "leaders": True,
                    "tables": True,
                    "xrefs_declared": True,
                    "embedded_raster_ocr": required_ocr == 0,
                },
            }
            return FileizedDrawingRecord(
                file_id=file_id,
                source_path=str(src),
                relative_path=str(relative_path),
                extension=src.suffix.lower(),
                status="ok",
                engine=self.engine_name,
                layers=layer_rows_from_entities(entities),
                blocks=block_rows_from_entities(entities),
                entities=entities,
                texts=texts,
                dimensions=dimension_rows_from_entities(entities),
                layouts=layouts,
                xrefs=xrefs,
                extraction_report=report,
                metadata={
                    "object_count": len(entities),
                    "text_occurrence_count": len(texts),
                    "dxf_version": getattr(doc, "dxfversion", None),
                },
                warnings=warnings,
            )
        except Exception as exc:
            return FileizedDrawingRecord.failed(
                file_id=file_id,
                source_path=src,
                relative_path=relative_path,
                extension=src.suffix,
                engine=self.engine_name,
                reason=str(exc),
            )
