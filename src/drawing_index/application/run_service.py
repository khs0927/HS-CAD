from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any

from src.corpus.schema import FileizedDrawingRecord
from src.corpus_run.pipeline_runner import CorpusPipelineRunner
from src.drawing_index.application.contracts import NullRunSummarySink, RunSummarySink
from src.drawing_index.domain.models import (
    FileIndexSummary,
    IndexRunSummary,
    utc_now_iso,
)


class DrawingIndexRunService:
    """Application-level orchestration for a complete drawing-index run."""

    def __init__(
        self,
        workspace: str | Path,
        *,
        runner: CorpusPipelineRunner | None = None,
        sink: RunSummarySink | None = None,
    ) -> None:
        self.workspace = Path(workspace)
        self.runner = runner or CorpusPipelineRunner(self.workspace)
        self.sink = sink or NullRunSummarySink()

    def run(
        self,
        root: str | Path,
        *,
        sample: int = 0,
        limit: int = 0,
        include_learning: bool = True,
        include_report: bool = True,
    ) -> dict[str, Any]:
        started_at = utc_now_iso()
        stages: dict[str, Any] = {
            "prepare": self.runner.prepare(root, sample=sample),
            "fileize": self.runner.fileize(limit=limit),
            "index": self.runner.index(),
        }
        if include_learning:
            stages["learn"] = self.runner.learn()
        if include_report:
            stages["report"] = self.runner.report()

        records = self._read_records()
        files = [FileIndexSummary.from_record(record) for record in records]
        summary = IndexRunSummary.build(
            workspace_id=self._workspace_id(),
            started_at=started_at,
            files=files,
            metadata={
                "root_fingerprint": self._path_fingerprint(Path(root)),
                "sample": sample,
                "limit": limit,
                "stage_results": stages,
            },
        )

        sink_result: dict[str, Any]
        try:
            sink_result = self.sink.publish(summary, files)
        except Exception as exc:
            sink_result = {
                "backend": type(self.sink).__name__,
                "published": False,
                "error": str(exc),
            }

        payload = summary.to_dict()
        payload["stages"] = stages
        payload["summary_sink"] = sink_result
        self.workspace.mkdir(parents=True, exist_ok=True)
        summary_path = self.workspace / "DRAWING_INDEX_RUN_SUMMARY.json"
        summary_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return {
            "run_id": summary.run_id,
            "status": summary.status,
            "summary": str(summary_path),
            "file_count": summary.file_count,
            "complete_count": summary.complete_count,
            "review_count": summary.review_count,
            "stages": stages,
            "summary_sink": sink_result,
        }

    def _read_records(self) -> list[FileizedDrawingRecord]:
        records: list[FileizedDrawingRecord] = []
        json_dir = self.workspace / "fileized" / "json"
        for path in sorted(json_dir.glob("*.json")):
            payload = json.loads(path.read_text(encoding="utf-8"))
            records.append(FileizedDrawingRecord(**payload))
        return records

    def _workspace_id(self) -> str:
        explicit = os.getenv("HSCAD_WORKSPACE_ID", "").strip()
        if explicit:
            return explicit
        return self._path_fingerprint(self.workspace)

    @staticmethod
    def _path_fingerprint(path: Path) -> str:
        normalized = str(path.expanduser().resolve()).replace("\\", "/").casefold()
        return "sha256:" + hashlib.sha256(normalized.encode("utf-8")).hexdigest()
