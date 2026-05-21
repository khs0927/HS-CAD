"""Placeholder for corpus query functionality.

A real implementation would parse the natural‑language query, translate it to
SQL/FTS statements and return matching knowledge records.  This stub simply
loads the SQLite database and prints a message.
"""

from __future__ import annotations

from pathlib import Path
import sqlite3
import json


def query_corpus(kb_path: Path, query: str) -> dict:
    """Execute a dummy query.

    Returns a dictionary with the original query and a placeholder result.
    """

    # Ensure the database exists – otherwise raise a clear error.
    if not kb_path.is_file():
        raise FileNotFoundError(f"Knowledge base not found: {kb_path}")
    # Open connection (not used for real query in this placeholder).
    conn = sqlite3.connect(kb_path)
    conn.close()
    return {
        "query": query,
        "result": "Placeholder – real query engine not implemented yet.",
    }
