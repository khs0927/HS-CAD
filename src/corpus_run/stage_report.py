"""Stage: generate the final markdown report for the run."""

from __future__ import annotations

from pathlib import Path

from src.corpus.report_builder import build_report


def run_report(workspace: Path | str, company_profile_path: str | None = None) -> dict:
    """Generate a final report markdown file.

    The report is written to ``workspace / "FINAL_REPORT.md"``.
    Returns a dict with the report path and text.
    """
    ws = Path(workspace)
    kb_path = ws / "corpus" / "cad_knowledge.sqlite"
    out_path = ws / "FINAL_REPORT.md"
    text = build_report(kb_path, out_path, company_profile_path=company_profile_path)
    return {"report_path": out_path, "summary": text}
