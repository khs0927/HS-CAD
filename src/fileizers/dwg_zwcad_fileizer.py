from __future__ import annotations

import os
import platform
from pathlib import Path

from src.adapters.zwcad_com_adapter import ZWCADCOMAdapter
from src.adapters.zwcad_complete_corpus_scanner import ZWCADCompleteCorpusScanner
from src.corpus.schema import (
    FileizedDrawingRecord,
    block_rows_from_entities,
    dimension_rows_from_entities,
    layer_rows_from_entities,
    text_rows_from_entities,
)
from src.fileizers.base import DrawingFileizer


class ZWCADDWGFileizer(DrawingFileizer):
    """Completeness-oriented native DWG fileizer."""

    engine_name = "zwcad_com_complete"
    supported_extensions = (".dwg",)

    def is_available(self) -> tuple[bool, str]:
        if platform.system() != "Windows":
            return False, "ZWCAD COM requires Windows"
        errors: list[str] = []
        try:
            import win32com.client  # noqa: F401

            return True, "pywin32 COM binding available"
        except Exception as exc:
            errors.append(f"pywin32={exc}")
        try:
            import comtypes.client  # noqa: F401

            return True, "comtypes COM binding available"
        except Exception as exc:
            errors.append(f"comtypes={exc}")
        return False, "Windows COM bindings unavailable: " + "; ".join(errors)

    @staticmethod
    def _open_read_only(adapter: ZWCADCOMAdapter, path: Path) -> tuple[bool, str | None]:
        absolute = os.path.abspath(path).replace("/", "\\")
        try:
            adapter.doc = adapter.app.Documents.Open(absolute, True)
            return True, None
        except Exception as read_only_error:
            # Some ZWCAD COM versions expose a one-argument Open method only.
            # The fallback remains non-mutating, but the record is intentionally
            # marked incomplete so the weaker lock mode is visible to reviewers.
            adapter.open_document(absolute)
            return False, str(read_only_error)

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

        adapter = ZWCADCOMAdapter(visible=False)
        try:
            adapter.connect()
            opened_read_only, read_only_error = self._open_read_only(adapter, src)
            result = ZWCADCompleteCorpusScanner(adapter).scan_document()
            entities = result["entities"]
            texts = text_rows_from_entities(entities)
            warnings = [*adapter.warnings, *result["warnings"]]
            if not opened_read_only:
                warnings.append(
                    {
                        "type": "read_only_open_unavailable",
                        "reason": read_only_error,
                    }
                )
            report = dict(result["report"])
            report["text_occurrence_count"] = len(texts)
            report["opened_read_only"] = opened_read_only
            report["adapter_warning_count"] = len(adapter.warnings)
            report["warning_count"] = int(report.get("warning_count", 0)) + len(
                adapter.warnings
            ) + (0 if opened_read_only else 1)
            report["complete"] = (
                bool(report.get("complete", False))
                and opened_read_only
                and not warnings
            )
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
                    "opened_read_only": opened_read_only,
                    "cad_product": str(
                        ZWCADCompleteCorpusScanner._safe_get(
                            adapter.app, "Name", "ZWCAD"
                        )
                    ),
                    "cad_version": str(
                        ZWCADCompleteCorpusScanner._safe_get(
                            adapter.app, "Version", ""
                        )
                    ),
                    "active_progid": adapter.active_progid,
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
        finally:
            adapter.close()
