from __future__ import annotations

from pathlib import Path

from src.corpus.indexer import CorpusIndexer
from src.corpus.query import CorpusQuery
from src.corpus.report_builder import CorpusReportBuilder
from src.corpus.schema import FileizedDrawingRecord
from src.corpus_run.manifest import ManifestEntry, read_manifest, scan_manifest, write_manifest
from src.fileizers.base import FileizedRecordWriter
from src.fileizers.dwg_zwcad_fileizer import ZWCADDWGFileizer
from src.fileizers.dxf_ezdxf_fileizer import DXFEzdxfFileizer


class CorpusPipelineRunner:
    def __init__(self, workspace: str | Path):
        self.workspace = Path(workspace)
        self.manifest_path = self.workspace / 'run_manifest.json'
        self.sqlite_path = self.workspace / 'cad_knowledge.sqlite'
        self.writer = FileizedRecordWriter(self.workspace)
        self.fileizers = [ZWCADDWGFileizer(), DXFEzdxfFileizer()]

    def prepare(self, root: str | Path, *, sample: int = 0) -> dict:
        entries = scan_manifest(root, sample=sample)
        path = write_manifest(entries, self.manifest_path)
        return {'manifest': path, 'file_count': len(entries)}

    def fileize(self, *, limit: int = 0) -> dict:
        entries = read_manifest(self.manifest_path)
        if limit:
            entries = entries[:limit]
        counts = {'ok': 0, 'failed': 0, 'unavailable': 0}
        outputs: list[dict[str, str]] = []
        for entry in entries:
            record = self._fileize_entry(entry)
            outputs.append(self.writer.write(record))
            counts[record.status] += 1
        return {'processed': len(entries), **counts, 'outputs': outputs}

    def index(self) -> dict:
        json_dir = self.workspace / 'fileized' / 'json'
        count = CorpusIndexer(self.sqlite_path).index_json_dir(json_dir)
        return {'sqlite': str(self.sqlite_path), 'indexed': count}

    def query(self, text: str, *, limit: int = 20) -> dict:
        return CorpusQuery(self.sqlite_path).search_text(text, limit=limit)

    def report(self, out: str | Path | None = None) -> dict:
        target = Path(out) if out else self.workspace / 'FINAL_REPORT.md'
        path = CorpusReportBuilder(self.sqlite_path).write(target)
        return {'report': path}

    def run_all(self, root: str | Path, *, sample: int = 0, limit: int = 0) -> dict:
        return {
            'prepare': self.prepare(root, sample=sample),
            'fileize': self.fileize(limit=limit),
            'index': self.index(),
            'report': self.report(),
        }

    def _fileize_entry(self, entry: ManifestEntry) -> FileizedDrawingRecord:
        for fileizer in self.fileizers:
            if fileizer.supports(entry.source_path):
                return fileizer.fileize(entry.source_path, file_id=entry.file_id, relative_path=entry.relative_path)
        return FileizedDrawingRecord.unavailable(
            file_id=entry.file_id,
            source_path=entry.source_path,
            relative_path=entry.relative_path,
            extension=entry.extension,
            engine='none',
            reason=f'No fileizer registered for extension {entry.extension}',
        )
