"""Stage: query the corpus to build an evidence pack (and optionally plan output)."""

from __future__ import annotations

from pathlib import Path

from src.corpus.evidence_pack import build_evidence_pack


def run_query(
    workspace: Path | str,
    query: str,
    limit: int = 30,
) -> dict:
    """Build an evidence pack for *query*.

    Returns the ``EvidencePack`` instance.
    """
    ws = Path(workspace)
    kb_path = ws / "corpus" / "cad_knowledge.sqlite"
    out_dir = ws / "ops"
    pack = build_evidence_pack(kb_path, query, out_dir, limit=limit)
    return {"evidence_pack": pack}
