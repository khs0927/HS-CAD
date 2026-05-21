"""Corpus quality audit helpers."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import asdict, dataclass, field
from pathlib import Path


EXPECTED_TABLES = [
    "files",
    "fileized_records",
    "texts",
    "materials",
    "specifications",
    "dimensions",
    "situations",
    "canonical_elements",
    "detail_patterns",
    "architectural_lessons",
    "processing_errors",
]


@dataclass
class TableAudit:
    table: str
    exists: bool
    count: int = 0


@dataclass
class CorpusAuditReport:
    kb_path: str
    tables: list[TableAudit] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not any(not t.exists for t in self.tables)


def _connect(kb_path: str | Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(kb_path))
    conn.row_factory = sqlite3.Row
    return conn


def audit_corpus(kb_path: str | Path, out_dir: str | Path) -> CorpusAuditReport:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    report = CorpusAuditReport(kb_path=str(kb_path))
    conn = _connect(kb_path)
    try:
        for table in EXPECTED_TABLES:
            exists = conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone() is not None
            count = 0
            if exists:
                try:
                    count = int(conn.execute(f"SELECT COUNT(*) AS c FROM {table}").fetchone()["c"])
                except Exception:
                    count = 0
            report.tables.append(TableAudit(table=table, exists=exists, count=count))

        counts = {t.table: t.count for t in report.tables}
        for t in report.tables:
            if not t.exists:
                report.warnings.append(f"Missing table: {t.table}")
        if counts.get("texts", 0) == 0:
            report.warnings.append("No text records found. OCR/DXF/DWG text extraction may not be connected.")
        if counts.get("materials", 0) == 0:
            report.warnings.append("No material records found. material_extractor may need more input texts.")
        if counts.get("situations", 0) == 0:
            report.warnings.append("No situation tags found. situation_extractor may need tuning.")

        # FTS availability check
        fts_tables = [
            r["name"]
            for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE '%fts%'").fetchall()
        ]
        if not fts_tables:
            report.recommendations.append("FTS5 tables not detected. Query uses LIKE/token fallback; this is acceptable but slower.")
        if counts.get("fileized_records", 0) == 0:
            report.recommendations.append("Run fileize-folder and corpus-next/index-fileized to populate fileized_records.")
        if counts.get("architectural_lessons", 0) == 0:
            report.recommendations.append("Run corpus-next learn to create architectural lessons.")

        (out / "corpus_audit.json").write_text(
            json.dumps(
                {
                    "kb_path": report.kb_path,
                    "tables": [asdict(t) for t in report.tables],
                    "warnings": report.warnings,
                    "recommendations": report.recommendations,
                    "ok": report.ok,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        (out / "corpus_audit.md").write_text(render_audit_markdown(report), encoding="utf-8")
        return report
    finally:
        conn.close()


def render_audit_markdown(report: CorpusAuditReport) -> str:
    lines = ["# CAD Corpus Audit", ""]
    lines.append(f"- KB: `{report.kb_path}`")
    lines.append(f"- OK: `{report.ok}`")
    lines.append("")
    lines.append("## Tables")
    lines.append("")
    lines.append("| Table | Exists | Count |")
    lines.append("|---|---:|---:|")
    for table in report.tables:
        lines.append(f"| {table.table} | {table.exists} | {table.count} |")
    if report.warnings:
        lines.append("")
        lines.append("## Warnings")
        for w in report.warnings:
            lines.append(f"- {w}")
    if report.recommendations:
        lines.append("")
        lines.append("## Recommendations")
        for r in report.recommendations:
            lines.append(f"- {r}")
    return "\n".join(lines).rstrip() + "\n"
