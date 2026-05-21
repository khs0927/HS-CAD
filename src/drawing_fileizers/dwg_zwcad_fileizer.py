from __future__ import annotations

from pathlib import Path
from typing import Any, List, Dict

from .base import BaseDrawingFileizer
from .models import (
    FileizedDrawingRecord,
    FileizedEntity,
    FileizedText,
    FileizedDimension,
)
from .utils import stable_file_id, normalize_text

# Relative import of the COM adapter
from src.adapters.zwcad_com_adapter import ZWCADCOMAdapter


class ZWCADCOMFileizer(BaseDrawingFileizer):
    """DWG fileizer using ZWCAD COM.

    Reads DWG files through the ``ZWCADCOMAdapter`` (COM automation). The
    implementation extracts layers, blocks, entities, texts, and dimensions.
    All operations are read‑only; the source DWG is never modified or saved.
    """

    SUPPORTED = {".dwg"}

    def supports(self, path: Path) -> bool:
        return path.suffix.lower() in self.SUPPORTED

    # ----- Availability ----------------------------------------------------
    def is_available(self) -> bool:
        """Return ``True`` if the COM adapter can be instantiated.

        Checks that the ``comtypes`` package is present and that a ZWCAD COM
        object can be created. Any exception (missing package, COM registration,
        or connection failure) results in ``False``.
        """
        try:
            import comtypes.client  # noqa: F401
        except Exception:
            return False
        try:
            adapter = ZWCADCOMAdapter(visible=False)
            adapter.connect()
            adapter.close()
            return True
        except Exception:
            return False

    def get_unavailable_reason(self) -> str:
        """Provide a human‑readable reason when ``is_available`` is ``False``.
        """
        try:
            import comtypes.client  # noqa: F401
        except Exception:
            return "comtypes package not installed"
        try:
            adapter = ZWCADCOMAdapter(visible=False)
            adapter.connect()
            adapter.close()
            return "available"
        except Exception as exc:
            return f"COM connection failed: {exc}"

    def get_name(self) -> str:
        return "zwcad-com"

    def get_version(self) -> str:
        # No stable version information is exposed via COM; return placeholder.
        return "unknown"

    # ----- Fileization ----------------------------------------------------
    def fileize(self, path: Path, out_dir: Path) -> FileizedDrawingRecord:
        """Fileize a DWG file via the COM adapter.

        Returns a :class:`FileizedDrawingRecord`. If the COM infrastructure is
        unavailable the record is marked with status ``"unavailable"`` and a
        warning is added.
        """
        if not self.is_available():
            return FileizedDrawingRecord.failed(
                path,
                self.get_name(),
                self.get_unavailable_reason() or "ZWCAD COM not available",
                status="unavailable",
            )

        try:
            adapter = ZWCADCOMAdapter(visible=False)
            adapter.open_document(str(path))
            data: Dict[str, Any] = adapter.scan_modelspace()
            warnings: List[str] = list(adapter.warnings)

            raw_entities: List[Dict[str, Any]] = data.get("entities", [])

            layers_set: set[str] = set()
            block_set: set[str] = set()
            entities: List[FileizedEntity] = []
            texts: List[FileizedText] = []
            dimensions: List[FileizedDimension] = []
            hatches: List[Dict[str, Any]] = []

            for ent in raw_entities:
                handle = ent.get("handle")
                entity_type = ent.get("entity_type")
                layer = ent.get("layer")
                if layer:
                    layers_set.add(layer)

                if entity_type == "INSERT":
                    block_name = ent.get("name") or ent.get("effective_name")
                    if block_name:
                        block_set.add(block_name)

                geometry = {
                    k: v
                    for k, v in ent.items()
                    if k not in {"handle", "entity_type", "layer", "name", "effective_name", "text", "text_override", "measurement", "entity_name"}
                }

                fileized = FileizedEntity(
                    entity_id=handle,
                    entity_type=entity_type,
                    layer=layer,
                    block_name=ent.get("name") if entity_type == "INSERT" else None,
                    text=ent.get("text"),
                    geometry=geometry,
                    style={},
                    bbox=[],
                    source=self.get_name(),
                    confidence=1.0,
                )
                entities.append(fileized)

                if entity_type in {"TEXT", "MTEXT"} and ent.get("text"):
                    txt = ent["text"]
                    texts.append(
                        FileizedText(
                            text=txt,
                            normalized_text=normalize_text(txt),
                            layer=layer,
                            bbox=[],
                            source=handle,
                        )
                    )

                if entity_type == "DIMENSION":
                    raw_text = ent.get("text_override") or ent.get("measurement") or ""
                    dimensions.append(
                        FileizedDimension(
                            raw_text=str(raw_text),
                            measurement=str(raw_text) if raw_text else None,
                            layer=layer,
                            geometry=geometry,
                            source=handle,
                        )
                    )

                if entity_type == "HATCH":
                    hatches.append({"entity_id": handle, "layer": layer, "style": {}})

            layers = [{"name": name} for name in sorted(layers_set)]
            blocks = [{"name": name} for name in sorted(block_set)]

            record = FileizedDrawingRecord(
                file_id=stable_file_id(path),
                source_path=str(path),
                relative_path=path.name,
                extension=path.suffix.lower(),
                fileizer=self.get_name(),
                fileizer_version=self.get_version(),
                metadata={},
                layers=layers,
                blocks=blocks,
                layouts=[],
                entities=entities,
                texts=texts,
                dimensions=dimensions,
                hatches=hatches,
                geometry_summary={
                    "entity_count": len(entities),
                    "text_count": len(texts),
                    "dimension_count": len(dimensions),
                },
                warnings=warnings,
            )
            return record
        except Exception as exc:
            return FileizedDrawingRecord.failed(
                path,
                self.get_name(),
                f"ZWCAD COM fileize failed: {exc}",
            )
        finally:
            try:
                adapter.close()
            except Exception:
                pass
