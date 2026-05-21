"""Stage: audit corpus quality and build relationship graph."""

from __future__ import annotations

from pathlib import Path

from src.corpus.quality_audit import audit_corpus
from src.corpus.relationship_graph import build_relationship_graph


def run_audit(workspace: Path | str) -> dict:
    """Run corpus audit and graph building.

    Returns a dict with ``audit`` and ``graph`` objects.
    """
    ws = Path(workspace)
    kb_path = ws / "corpus" / "cad_knowledge.sqlite"
    out_dir = ws / "ops"
    audit_report = audit_corpus(kb_path, out_dir)
    graph = build_relationship_graph(kb_path, out_dir)
    return {"audit": audit_report, "graph": graph}
