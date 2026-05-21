"""Placeholder for corpus learning.

The real implementation would analyse the extracted knowledge records,
aggregate statistics, and generate lesson recommendations.  For now we
provide a minimal function that records that the step was executed.
"""

from __future__ import annotations

from pathlib import Path
import json


def learn_corpus(kb_path: Path, out_dir: Path) -> None:
    """Create a dummy learning output.

    ``kb_path`` points to the SQLite knowledge store.  ``out_dir`` receives a
    ``learning_summary.json`` file that contains a simple acknowledgment.
    """

    out_dir.mkdir(parents=True, exist_ok=True)
    summary = {
        "status": "completed",
        "message": "Learning step placeholder – no real analysis performed.",
        "knowledge_store": str(kb_path),
    }
    (out_dir / "learning_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
