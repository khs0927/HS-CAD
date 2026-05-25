from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from src.analysis.entity_loader import write_json_and_md


WINDOWS_PATH_RE = re.compile(r"[A-Za-z]:[\\/][^\n\r\"']+")
GOOGLE_DRIVE_RE = re.compile(r"(내 드라이브|#웹하드|Google Drive|구글 드라이브)", re.IGNORECASE)


def build_report_redaction_plan(workspace: str | Path, *, apply_redaction: bool = False) -> dict[str, Any]:
    base = Path(workspace)
    candidates = []
    for pattern in ["*.json", "*.md", "*.html", "worker_logs/*.jsonl", "worker_pipeline_logs/*.log"]:
        for path in sorted(base.glob(pattern)):
            if not path.is_file():
                continue
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
            except Exception:
                continue
            hits = _find_sensitive_hits(text)
            if hits:
                candidates.append({
                    "path": str(path),
                    "relative_path": str(path.relative_to(base)),
                    "hit_count": len(hits),
                    "hits_sample": hits[:10],
                })
                if apply_redaction:
                    path.write_text(_redact_text(text), encoding="utf-8")

    payload = {
        "backend": "report_redactor",
        "schema_version": "0.1",
        "parameters": {"apply_redaction": apply_redaction},
        "summary": {
            "candidate_file_count": len(candidates),
            "total_hit_count": sum(int(row["hit_count"]) for row in candidates),
            "redaction_applied": apply_redaction,
        },
        "candidates": candidates,
        "todo": [
            "Add configurable redaction patterns.",
            "Add path hashing for reproducible private path masking.",
            "Add backup file creation before apply_redaction=True.",
            "Add tests with Korean/Windows path samples.",
        ],
        "warnings": [] if not apply_redaction else ["Redaction was applied to generated artifacts only."],
    }
    return write_json_and_md(base, "REPORT_REDACTION_PLAN", payload, _markdown(payload))


def _find_sensitive_hits(text: str) -> list[str]:
    hits: list[str] = []
    hits.extend(WINDOWS_PATH_RE.findall(text))
    if GOOGLE_DRIVE_RE.search(text):
        hits.append("google_drive_or_webhard_keyword")
    return list(dict.fromkeys(hit[:200] for hit in hits))


def _redact_text(text: str) -> str:
    text = WINDOWS_PATH_RE.sub("<REDACTED_WINDOWS_PATH>", text)
    text = GOOGLE_DRIVE_RE.sub("<REDACTED_DRIVE_KEYWORD>", text)
    return text


def _markdown(payload: dict[str, Any]) -> str:
    s = payload.get("summary") or {}
    lines = [
        "# Report Redaction Plan",
        "",
        f"- Candidate files: `{s.get('candidate_file_count')}`",
        f"- Total hits: `{s.get('total_hit_count')}`",
        f"- Redaction applied: `{s.get('redaction_applied')}`",
        "",
        "| File | Hits |",
        "|---|---:|",
    ]
    for row in payload.get("candidates") or []:
        lines.append(f"| {row.get('relative_path')} | {row.get('hit_count')} |")
    lines.append("")
    return "\n".join(lines)
