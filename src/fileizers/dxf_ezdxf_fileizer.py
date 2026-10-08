from __future__ import annotations

from pathlib import Path

from src.adapters.ezdxf_corpus_scanner import EzdxfCorpusScanner
from src.corpus.schema import (
    FileizedDrawingRecord,
    block_rows_from_entities,
    dimension_rows_from_entities,
    layer_rows_from_entities,
    text_rows_from_entities,
)
from src.fileizers.base import DrawingFileizer


class DXFEzdxfFileizer(DrawingFileizer):
    """Completeness-oriented DXF fileizer using the ezdxf adapter."""

    engine_name = "ezdxf_complete"
    supported_extensions = (".dxf",)

    def is_available(self) -> tuple[bool, str]:
        try:
            import ezdxf  # noqa: F401

            return True, "ezdxf available"
        except Exception as exc:
            return False, f"ezdxf unavailable: {exc}"

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
            result = EzdxfCorpusScanner(doc).scan()
            entities = result["entities"]
            texts = text_rows_from_entities(entities)
            report = dict(result["report"])
            report["text_occurrence_count"] = len(texts)
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
                layouts=result["layouts"],
                xrefs=result["xrefs"],
                extraction_report=report,
                metadata={
                    "object_count": len(entities),
                    "text_occurrence_count": len(texts),
                    "dxf_version": getattr(doc, "dxfversion", None),
                },
                warnings=result["warnings"],
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
