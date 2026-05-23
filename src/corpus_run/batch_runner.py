from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from src.corpus.quality import CorpusQualityAuditor
from src.corpus.validator import FileizedRecordValidator
from src.corpus_run.manifest import read_manifest
from src.corpus_run.pipeline_runner import CorpusPipelineRunner
from src.corpus_run.result_summarizer import CorpusRunResultSummarizer


@dataclass
class BatchItem:
    batch_index: int
    offset: int
    limit: int
    status: str
    result: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class CorpusBatchRunner:
    def __init__(self, workspace: str | Path):
        self.workspace = Path(workspace)
        self.runner = CorpusPipelineRunner(self.workspace)

    def run_batches(
        self,
        *,
        batch_size: int = 50,
        max_batches: int = 1,
        start_offset: int = 0,
        skip_existing: bool = True,
        finalize: bool = True,
    ) -> dict[str, Any]:
        entries = read_manifest(self.workspace / 'run_manifest.json')
        items: list[BatchItem] = []
        offset = max(0, start_offset)
        batch_size = max(1, batch_size)
        max_batches = max(1, max_batches)
        for batch_index in range(max_batches):
            if offset >= len(entries):
                break
            try:
                result = self.runner.fileize(limit=batch_size, offset=offset, skip_existing=skip_existing)
                status = 'ok'
            except Exception as exc:
                result = {'error': str(exc)}
                status = 'failed'
            items.append(BatchItem(batch_index=batch_index, offset=offset, limit=batch_size, status=status, result=result))
            offset += batch_size
            if status != 'ok':
                break
        final: dict[str, Any] = {}
        if finalize:
            final = self._finalize()
        payload = {
            'workspace': str(self.workspace),
            'manifest_count': len(entries),
            'batch_size': batch_size,
            'max_batches': max_batches,
            'start_offset': start_offset,
            'next_offset': offset,
            'skip_existing': skip_existing,
            'batches': [item.to_dict() for item in items],
            'finalize': final,
        }
        self.write_log(payload)
        return payload

    def _finalize(self) -> dict[str, Any]:
        out: dict[str, Any] = {}
        validation = FileizedRecordValidator().validate_json_dir(self.workspace / 'fileized' / 'json')
        out['validate'] = validation
        if validation.get('invalid_count'):
            return out
        out['index'] = self.runner.index()
        out['learn'] = self.runner.learn()
        auditor = CorpusQualityAuditor(self.workspace)
        out['quality'] = {'json': auditor.write_json(), 'markdown': auditor.write_markdown()}
        out['report'] = self.runner.report()
        summarizer = CorpusRunResultSummarizer(self.workspace)
        out['summary'] = {'json': summarizer.write_json(), 'markdown': summarizer.write_markdown()}
        return out

    def write_log(self, payload: dict[str, Any]) -> str:
        path = self.workspace / 'BATCH_RUN.json'
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
        return str(path)
