from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

from src.corpus.evidence import EvidencePackageBuilder
from src.corpus.indexer import CorpusIndexer
from src.corpus.learner import CorpusLearner
from src.corpus.query import CorpusQuery
from src.corpus.report_builder import CorpusReportBuilder
from src.corpus.schema import FileizedDrawingRecord
from src.corpus_run.manifest import ManifestEntry, read_manifest, scan_manifest, write_manifest
from src.drawing_index.application.fileizer_registry import FileizerRegistry
from src.fileizers.base import DrawingFileizer, FileizedRecordWriter
from src.fileizers.dwg_dxf_ezdxf_fileizer import DWGToDXFEzdxfFileizer
from src.fileizers.dwg_zwcad_fileizer import ZWCADDWGFileizer
from src.fileizers.dxf_ezdxf_fileizer import DXFEzdxfFileizer
from src.fileizers.image_fileizer import ImageMetadataFileizer
from src.fileizers.pdf_pymupdf_fileizer import PDFPyMuPDFFileizer


class CorpusPipelineRunner:
    def __init__(
        self,
        workspace: str | Path,
        *,
        include_com_fallback: bool = True,
        fileizers: Iterable[DrawingFileizer] | None = None,
    ):
        self.workspace = Path(workspace)
        self.manifest_path = self.workspace / "run_manifest.json"
        self.sqlite_path = self.workspace / "cad_knowledge.sqlite"
        self.writer = FileizedRecordWriter(self.workspace)

        if fileizers is None:
            configured: list[DrawingFileizer] = []
            if include_com_fallback:
                configured.append(ZWCADDWGFileizer())
            configured.extend(
                [
                    DWGToDXFEzdxfFileizer(temp_root=self.workspace / "tmp" / "dxf"),
                    DXFEzdxfFileizer(),
                    PDFPyMuPDFFileizer(),
                    ImageMetadataFileizer(),
                ]
            )
        else:
            configured = list(fileizers)
        self.registry = FileizerRegistry(configured)
        # Backwards-compatible read-only snapshot for callers that inspect the
        # configured engines.
        self.fileizers = list(self.registry.fileizers)

    def prepare(self, root: str | Path, *, sample: int = 0) -> dict:
        entries = scan_manifest(root, sample=sample)
        path = write_manifest(entries, self.manifest_path)
        return {"manifest": path, "file_count": len(entries)}

    def fileize(
        self,
        *,
        limit: int = 0,
        offset: int = 0,
        skip_existing: bool = False,
    ) -> dict:
        entries = read_manifest(self.manifest_path)
        total_manifest_entries = len(entries)
        if offset:
            entries = entries[offset:]
        if limit:
            entries = entries[:limit]
        counts = {"ok": 0, "failed": 0, "unavailable": 0, "skipped": 0}
        complete_count = 0
        review_count = 0
        outputs: list[dict[str, str]] = []
        for entry in entries:
            if skip_existing and self._is_existing_success(entry.file_id):
                counts["skipped"] += 1
                outputs.append(
                    {
                        "skipped": str(
                            self.workspace
                            / "fileized"
                            / "json"
                            / f"{entry.file_id}.json"
                        )
                    }
                )
                continue
            record = self._fileize_entry(entry)
            outputs.append(self.writer.write(record))
            counts[record.status] = counts.get(record.status, 0) + 1
            if record.status == "ok" and bool(
                (record.extraction_report or {}).get("complete")
            ):
                complete_count += 1
            else:
                review_count += 1
        return {
            "processed": len(entries),
            "offset": offset,
            "limit": limit,
            "total_manifest_entries": total_manifest_entries,
            "complete": complete_count,
            "review": review_count,
            **counts,
            "outputs": outputs,
        }

    def index(self) -> dict:
        json_dir = self.workspace / "fileized" / "json"
        count = CorpusIndexer(self.sqlite_path).index_json_dir(json_dir)
        return {"sqlite": str(self.sqlite_path), "indexed": count}

    def learn(self, out: str | Path | None = None) -> dict:
        target = Path(out) if out else self.workspace / "learning_summary.json"
        path = CorpusLearner(self.sqlite_path).write(target)
        return {"learning_summary": path}

    def query(self, text: str, *, limit: int = 20) -> dict:
        return CorpusQuery(self.sqlite_path).search_text(text, limit=limit)

    def evidence(self, text: str, *, limit: int = 20) -> dict:
        return EvidencePackageBuilder(self.sqlite_path).build(text, limit=limit)

    def report(self, out: str | Path | None = None) -> dict:
        target = Path(out) if out else self.workspace / "FINAL_REPORT.md"
        path = CorpusReportBuilder(self.sqlite_path).write(target)
        return {"report": path}

    def run_all(
        self,
        root: str | Path,
        *,
        sample: int = 0,
        limit: int = 0,
    ) -> dict:
        return {
            "prepare": self.prepare(root, sample=sample),
            "fileize": self.fileize(limit=limit),
            "index": self.index(),
            "learn": self.learn(),
            "report": self.report(),
        }

    def _fileize_entry(self, entry: ManifestEntry) -> FileizedDrawingRecord:
        return self.registry.fileize(
            entry.source_path,
            file_id=entry.file_id,
            relative_path=entry.relative_path,
        )

    def _is_existing_success(self, file_id: str) -> bool:
        path = self.workspace / "fileized" / "json" / f"{file_id}.json"
        if not path.exists():
            return False
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            return payload.get("status") == "ok" and bool(
                (payload.get("extraction_report") or {}).get("complete")
            )
        except Exception:
            return False
