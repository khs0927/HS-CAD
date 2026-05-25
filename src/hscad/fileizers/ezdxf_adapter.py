from __future__ import annotations

from pathlib import Path
from typing import Any

from src.hscad.fileizers.models import FileizedDrawing, FileizedEntity, layer_counts


class EzdxfAdapter:
    engine_name = "ezdxf"

    def is_available(self) -> tuple[bool, str]:
        try:
            import ezdxf  # noqa: F401
            return True, "ezdxf available"
        except Exception as exc:
            return False, f"ezdxf unavailable: {exc}"

    def read_dxf(self, path: str | Path) -> FileizedDrawing:
        src = Path(path)
        ok, reason = self.is_available()
        if not ok:
            return FileizedDrawing.unavailable(src, source_type="dxf", engine=self.engine_name, reason=reason)
        try:
            import ezdxf

            doc = ezdxf.readfile(str(src))
            entities = [self._entity_to_model(entity) for entity in doc.modelspace()]
            return FileizedDrawing(
                source_path=str(src),
                source_type="dxf",
                status="ok",
                engine=self.engine_name,
                normalized_entities=entities,
                layers=layer_counts(entities),
                texts=[
                    {"handle": e.handle, "layer": e.layer, "text": e.properties.get("text")}
                    for e in entities
                    if e.properties.get("text")
                ],
                metadata={"dxf_version": getattr(doc, "dxfversion", None), "entity_count": len(entities)},
            )
        except Exception as exc:
            return FileizedDrawing.failed(src, source_type="dxf", engine=self.engine_name, reason=str(exc))

    def _entity_to_model(self, entity: Any) -> FileizedEntity:
        etype = str(entity.dxftype()).upper()
        properties: dict[str, Any] = {"color": getattr(entity.dxf, "color", None)}
        geometry: dict[str, Any] = {}
        if etype == "LINE":
            geometry["start"] = _xyz(entity.dxf.start)
            geometry["end"] = _xyz(entity.dxf.end)
        if etype in {"TEXT", "MTEXT"}:
            properties["text"] = getattr(entity.dxf, "text", None) or getattr(entity, "text", "")
        return FileizedEntity(
            entity_type=etype,
            layer=str(getattr(entity.dxf, "layer", "0")),
            handle=str(getattr(entity.dxf, "handle", "")) or None,
            geometry=geometry,
            properties=properties,
            evidence=[{"source": "ezdxf", "confidence": 0.9}],
        )


def _xyz(value: Any) -> list[float] | None:
    try:
        return [float(value[0]), float(value[1]), float(value[2] if len(value) > 2 else 0.0)]
    except Exception:
        return None

