from __future__ import annotations

from pathlib import Path
from typing import Any

from .base import BaseDrawingFileizer
from .models import FileizedDimension, FileizedDrawingRecord, FileizedEntity, FileizedText
from .utils import normalize_text, stable_file_id


class DXFFileizer(BaseDrawingFileizer):
    """DXF fileizer powered by ezdxf.

    This module reads DXF files and extracts raw drawing information. It does
    not apply ZIUM/company style. That mapping happens later.
    """

    SUPPORTED = {".dxf"}

    def supports(self, path: Path) -> bool:
        return path.suffix.lower() in self.SUPPORTED

    def is_available(self) -> bool:
        try:
            import ezdxf  # noqa: F401

            return True
        except Exception:
            return False

    def get_name(self) -> str:
        return "ezdxf"

    def get_version(self) -> str:
        try:
            import ezdxf

            return getattr(ezdxf, "__version__", "unknown")
        except Exception:
            return "unavailable"

    def fileize(self, path: Path, out_dir: Path) -> FileizedDrawingRecord:
        path = Path(path)
        if not self.is_available():
            return FileizedDrawingRecord.failed(path, self.get_name(), "ezdxf is not installed", status="unavailable")

        try:
            import ezdxf

            doc = ezdxf.readfile(path)
            entities: list[FileizedEntity] = []
            texts: list[FileizedText] = []
            dimensions: list[FileizedDimension] = []
            hatches: list[dict[str, Any]] = []

            layers = [{"name": layer.dxf.name, "color": getattr(layer.dxf, "color", None)} for layer in doc.layers]
            blocks = [{"name": block.name, "entity_count": len(list(block))} for block in doc.blocks]
            layouts = [{"name": layout.name, "entity_count": len(list(layout))} for layout in doc.layouts]

            for space_name, space in [("modelspace", doc.modelspace())]:
                for index, entity in enumerate(space):
                    item = self._entity_to_fileized(entity, f"{space_name}:{index}")
                    entities.append(item)

                    if item.entity_type in {"TEXT", "MTEXT"} and item.text:
                        texts.append(
                            FileizedText(
                                text=item.text,
                                normalized_text=normalize_text(item.text),
                                layer=item.layer,
                                bbox=item.bbox,
                                source=item.entity_id,
                            )
                        )

                    if item.entity_type == "DIMENSION":
                        dim_text = item.text or item.geometry.get("measurement") or ""
                        dimensions.append(
                            FileizedDimension(
                                raw_text=str(dim_text),
                                measurement=str(dim_text) if dim_text else None,
                                layer=item.layer,
                                geometry=item.geometry,
                                source=item.entity_id,
                            )
                        )

                    if item.entity_type == "HATCH":
                        hatches.append({"entity_id": item.entity_id, "layer": item.layer, "style": item.style})

            metadata = {
                "dxfversion": doc.dxfversion,
                "encoding": getattr(doc, "encoding", None),
                "acad_release": getattr(doc, "acad_release", None),
            }

            record = FileizedDrawingRecord(
                file_id=stable_file_id(path),
                source_path=str(path),
                relative_path=path.name,
                extension=path.suffix.lower(),
                fileizer=self.get_name(),
                fileizer_version=self.get_version(),
                metadata=metadata,
                layers=layers,
                blocks=blocks,
                layouts=layouts,
                entities=entities,
                texts=texts,
                dimensions=dimensions,
                hatches=hatches,
                geometry_summary={"entity_count": len(entities), "text_count": len(texts), "dimension_count": len(dimensions)},
            )
            return record
        except Exception as exc:
            return FileizedDrawingRecord.failed(path, self.get_name(), f"DXF fileize failed: {exc}")

    def _entity_to_fileized(self, entity: Any, entity_id: str) -> FileizedEntity:
        etype = entity.dxftype()
        layer = getattr(entity.dxf, "layer", None)
        text = None
        geometry: dict[str, Any] = {}
        style: dict[str, Any] = {}
        bbox: list[float] = []

        if etype == "LINE":
            geometry = {"start": list(entity.dxf.start), "end": list(entity.dxf.end)}
        elif etype in {"LWPOLYLINE", "POLYLINE"}:
            try:
                geometry = {"points": [list(p[:2]) for p in entity.get_points()]}
            except Exception:
                geometry = {"points": []}
        elif etype == "TEXT":
            text = str(entity.dxf.text)
            geometry = {"insert": list(entity.dxf.insert)}
            style = {"height": getattr(entity.dxf, "height", None), "style": getattr(entity.dxf, "style", None)}
        elif etype == "MTEXT":
            text = entity.text
            geometry = {"insert": list(entity.dxf.insert)}
            style = {"char_height": getattr(entity.dxf, "char_height", None), "style": getattr(entity.dxf, "style", None)}
        elif etype == "DIMENSION":
            text = getattr(entity.dxf, "text", "") or ""
            geometry = {
                "defpoint": self._maybe_list(getattr(entity.dxf, "defpoint", None)),
                "defpoint2": self._maybe_list(getattr(entity.dxf, "defpoint2", None)),
                "defpoint3": self._maybe_list(getattr(entity.dxf, "defpoint3", None)),
                "measurement": text,
            }
            style = {"dimstyle": getattr(entity.dxf, "dimstyle", None)}
        elif etype == "INSERT":
            geometry = {
                "insert": self._maybe_list(getattr(entity.dxf, "insert", None)),
                "rotation": getattr(entity.dxf, "rotation", 0.0),
                "xscale": getattr(entity.dxf, "xscale", 1.0),
                "yscale": getattr(entity.dxf, "yscale", 1.0),
            }
            style = {"name": getattr(entity.dxf, "name", None)}
        elif etype == "HATCH":
            style = {"pattern_name": getattr(entity.dxf, "pattern_name", None), "solid_fill": getattr(entity.dxf, "solid_fill", None)}
        elif etype == "ARC":
            geometry = {
                "center": self._maybe_list(getattr(entity.dxf, "center", None)),
                "radius": getattr(entity.dxf, "radius", None),
                "start_angle": getattr(entity.dxf, "start_angle", None),
                "end_angle": getattr(entity.dxf, "end_angle", None),
            }
        elif etype == "CIRCLE":
            geometry = {"center": self._maybe_list(getattr(entity.dxf, "center", None)), "radius": getattr(entity.dxf, "radius", None)}

        block_name = None
        if etype == "INSERT":
            block_name = getattr(entity.dxf, "name", None)

        return FileizedEntity(
            entity_id=entity_id,
            entity_type=etype,
            layer=layer,
            block_name=block_name,
            text=text,
            geometry=geometry,
            style=style,
            bbox=bbox,
            source="ezdxf",
            confidence=1.0,
        )

    @staticmethod
    def _maybe_list(value: Any) -> list[float]:
        if value is None:
            return []
        try:
            return list(value)
        except TypeError:
            return []
