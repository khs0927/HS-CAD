"""Placeholder for building a markdown report from the corpus.

Generates a simple markdown file summarising the corpus size and a few stub
statistics.
"""

from __future__ import annotations

from pathlib import Path
import json


def build_report(kb_path: Path, out_path: Path) -> None:
    """Write a minimal markdown report.

    ``kb_path`` – path to the SQLite store (used only for existence check).
    ``out_path`` – destination markdown file.
    """

    if not kb_path.is_file():
        raise FileNotFoundError(f"Knowledge store not found: {kb_path}")
    # Basic placeholder data – in real implementation we would query the DB.
    report_lines = [
        "# CAD Corpus Report",
        "",
        f"Knowledge store: `{kb_path}`",
        "",
        "* This is a placeholder report.\n",
        "* Implement detailed statistics, top materials, situation tags, etc.",
    ]
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(report_lines), encoding="utf-8")
