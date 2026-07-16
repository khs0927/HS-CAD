from __future__ import annotations

import hashlib
import os
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

import requests

from src.drawing_index.application.contracts import RunSummarySink
from src.drawing_index.domain.models import FileIndexSummary, IndexRunSummary


@dataclass(frozen=True)
class SupabaseSummarySettings:
    url: str
    service_role_key: str
    timeout_seconds: float = 30.0
    batch_size: int = 200

    @classmethod
    def from_env(cls) -> SupabaseSummarySettings | None:
        url = os.getenv("HSCAD_SUPABASE_URL", "").strip().rstrip("/")
        key = os.getenv("HSCAD_SUPABASE_SERVICE_ROLE_KEY", "").strip()
        if not url or not key:
            return None
        timeout = float(os.getenv("HSCAD_SUPABASE_TIMEOUT", "30"))
        batch_size = max(1, min(1000, int(os.getenv("HSCAD_SUPABASE_BATCH_SIZE", "200"))))
        return cls(url=url, service_role_key=key, timeout_seconds=timeout, batch_size=batch_size)

    def validate(self) -> None:
        parsed = urlparse(self.url)
        if parsed.scheme != "https" or not parsed.netloc:
            raise ValueError("HSCAD_SUPABASE_URL must be an absolute HTTPS URL")
        if len(self.service_role_key) < 20:
            raise ValueError("HSCAD_SUPABASE_SERVICE_ROLE_KEY is missing or invalid")


class SupabaseRunSummarySink(RunSummarySink):
    """Publish aggregate statistics without uploading drawing identifiers.

    Relative paths remain available to the local SQLite history but are replaced
    with a fixed marker remotely. Workspace labels and local file IDs are hashed
    again at the remote boundary so operator labels and deterministic path hashes
    cannot be correlated across runs. The service-role key is accepted only
    through environment variables and must never be bundled into a client.
    """

    backend = "supabase_rest"
    REDACTED_PATH = "<redacted>"

    def __init__(
        self,
        settings: SupabaseSummarySettings,
        *,
        session: requests.Session | None = None,
    ) -> None:
        settings.validate()
        self.settings = settings
        self.session = session or requests.Session()

    @classmethod
    def from_env(cls) -> SupabaseRunSummarySink | None:
        settings = SupabaseSummarySettings.from_env()
        return None if settings is None else cls(settings)

    def publish(
        self,
        run: IndexRunSummary,
        files: Sequence[FileIndexSummary],
    ) -> dict[str, Any]:
        self._upsert("cad_index_runs", [self._run_row(run)], "run_id")
        published = 0
        rows = [self._file_row(run.run_id, item) for item in files]
        for start in range(0, len(rows), self.settings.batch_size):
            batch = rows[start : start + self.settings.batch_size]
            self._upsert("cad_index_files", batch, "run_id,file_id")
            published += len(batch)
        return {
            "backend": self.backend,
            "published": True,
            "run_id": run.run_id,
            "file_count": published,
        }

    def _upsert(self, table: str, rows: list[dict[str, Any]], conflict: str) -> None:
        if not rows:
            return
        response = self.session.post(
            f"{self.settings.url}/rest/v1/{table}",
            params={"on_conflict": conflict},
            headers={
                "apikey": self.settings.service_role_key,
                "Authorization": f"Bearer {self.settings.service_role_key}",
                "Content-Type": "application/json",
                "Prefer": "resolution=merge-duplicates,return=minimal",
                "User-Agent": "hs-cad-drawing-index/0.4",
            },
            json=rows,
            timeout=self.settings.timeout_seconds,
        )
        if response.status_code >= 300:
            detail = response.text[:1000]
            raise RuntimeError(
                f"Supabase summary upsert failed for {table}: "
                f"HTTP {response.status_code}: {detail}"
            )

    @classmethod
    def _run_row(cls, run: IndexRunSummary) -> dict[str, Any]:
        return {
            "run_id": run.run_id,
            "workspace_id": cls._hash_token("workspace", run.workspace_id),
            "started_at": run.started_at,
            "completed_at": run.completed_at,
            "status": run.status,
            "file_count": run.file_count,
            "complete_count": run.complete_count,
            "review_count": run.review_count,
            "failed_count": run.failed_count,
            "unavailable_count": run.unavailable_count,
            "total_entities": run.total_entities,
            "total_text_occurrences": run.total_text_occurrences,
            "metadata": run.metadata,
        }

    @classmethod
    def _file_row(cls, run_id: str, item: FileIndexSummary) -> dict[str, Any]:
        return {
            "run_id": run_id,
            "file_id": cls._hash_token("file", f"{run_id}:{item.file_id}"),
            "relative_path": cls.REDACTED_PATH,
            "extension": item.extension,
            "status": item.status,
            "engine": item.engine,
            "complete": item.complete,
            "entity_count": item.entity_count,
            "text_occurrence_count": item.text_occurrence_count,
            "layout_count": item.layout_count,
            "xref_count": item.xref_count,
            "warning_count": item.warning_count,
            "error_count": item.error_count,
            "requires_ocr_count": item.requires_ocr_count,
            "unsupported_proxy_count": item.unsupported_proxy_count,
            "unresolved_xref_count": item.unresolved_xref_count,
            "blockers": list(item.blockers),
            "extraction_report": item.extraction_report,
        }

    @staticmethod
    def _hash_token(namespace: str, value: str) -> str:
        digest = hashlib.sha256(f"{namespace}:{value}".encode("utf-8")).hexdigest()
        return f"sha256:{digest}"
