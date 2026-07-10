from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Iterable
from uuid import uuid4

from .models import JobRecord, JobStatus, WorkflowResult, WorkflowSpec, utc_now


class JobStore:
    """SQLite-backed queue safe for one or more worker processes."""

    def __init__(self, path: str | Path = "outputs/xicad_background/jobs.sqlite3") -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=30.0, isolation_level=None)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA busy_timeout=30000")
        return connection

    def _initialize(self) -> None:
        with self._connect() as db:
            db.execute(
                """
                CREATE TABLE IF NOT EXISTS jobs (
                    id TEXT PRIMARY KEY,
                    status TEXT NOT NULL,
                    workflow_json TEXT NOT NULL,
                    result_json TEXT,
                    error TEXT,
                    worker_id TEXT,
                    attempts INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            db.execute("CREATE INDEX IF NOT EXISTS idx_jobs_status_created ON jobs(status, created_at)")

    def enqueue(self, workflow: WorkflowSpec) -> JobRecord:
        job_id = uuid4().hex
        now = utc_now()
        with self._connect() as db:
            db.execute(
                "INSERT INTO jobs(id,status,workflow_json,created_at,updated_at) VALUES(?,?,?,?,?)",
                (job_id, JobStatus.pending.value, workflow.model_dump_json(), now, now),
            )
        return self.get(job_id)

    def get(self, job_id: str) -> JobRecord:
        with self._connect() as db:
            row = db.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
        if row is None:
            raise KeyError(f"Unknown XiCAD job: {job_id}")
        return self._row_to_record(row)

    def list(self, statuses: Iterable[JobStatus] | None = None, limit: int = 100) -> list[JobRecord]:
        with self._connect() as db:
            if statuses:
                values = [status.value for status in statuses]
                marks = ",".join("?" for _ in values)
                rows = db.execute(
                    f"SELECT * FROM jobs WHERE status IN ({marks}) ORDER BY created_at DESC LIMIT ?",
                    (*values, int(limit)),
                ).fetchall()
            else:
                rows = db.execute("SELECT * FROM jobs ORDER BY created_at DESC LIMIT ?", (int(limit),)).fetchall()
        return [self._row_to_record(row) for row in rows]

    def claim_next(self, worker_id: str) -> JobRecord | None:
        now = utc_now()
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT id FROM jobs WHERE status=? ORDER BY created_at LIMIT 1",
                (JobStatus.pending.value,),
            ).fetchone()
            if row is None:
                db.execute("COMMIT")
                return None
            updated = db.execute(
                """
                UPDATE jobs SET status=?, worker_id=?, attempts=attempts+1, updated_at=?
                WHERE id=? AND status=?
                """,
                (JobStatus.running.value, worker_id, now, row["id"], JobStatus.pending.value),
            ).rowcount
            db.execute("COMMIT")
        return self.get(row["id"]) if updated else None

    def complete(self, job_id: str, result: WorkflowResult) -> JobRecord:
        return self._finish(job_id, result.status, result=result)

    def fail(self, job_id: str, error: str, result: WorkflowResult | None = None) -> JobRecord:
        return self._finish(job_id, JobStatus.failed, result=result, error=error)

    def block(self, job_id: str, error: str) -> JobRecord:
        return self._finish(job_id, JobStatus.blocked, error=error)

    def cancel(self, job_id: str) -> JobRecord:
        with self._connect() as db:
            db.execute(
                "UPDATE jobs SET status=?, updated_at=? WHERE id=? AND status IN (?,?)",
                (JobStatus.cancelled.value, utc_now(), job_id, JobStatus.pending.value, JobStatus.blocked.value),
            )
        return self.get(job_id)

    def recover_abandoned(self) -> int:
        with self._connect() as db:
            result = db.execute(
                "UPDATE jobs SET status=?, worker_id=NULL, updated_at=? WHERE status=?",
                (JobStatus.pending.value, utc_now(), JobStatus.running.value),
            )
        return int(result.rowcount)

    def _finish(
        self,
        job_id: str,
        status: JobStatus,
        *,
        result: WorkflowResult | None = None,
        error: str | None = None,
    ) -> JobRecord:
        result_json = result.model_dump_json() if result else None
        with self._connect() as db:
            db.execute(
                "UPDATE jobs SET status=?, result_json=?, error=?, updated_at=? WHERE id=?",
                (status.value, result_json, error, utc_now(), job_id),
            )
        return self.get(job_id)

    @staticmethod
    def _row_to_record(row: sqlite3.Row) -> JobRecord:
        return JobRecord(
            id=row["id"],
            status=JobStatus(row["status"]),
            workflow=WorkflowSpec.model_validate_json(row["workflow_json"]),
            result=WorkflowResult.model_validate_json(row["result_json"]) if row["result_json"] else None,
            error=row["error"],
            worker_id=row["worker_id"],
            attempts=int(row["attempts"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
