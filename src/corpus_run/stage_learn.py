"""Stage: learn from the knowledge base (corpus)."""

from __future__ import annotations

from pathlib import Path

from src.corpus.corpus_learner import learn_from_kb


def run_learn(workspace: Path | str) -> dict:
    """Run the learning step.

    Returns the summary dict produced by ``learn_from_kb``.
    """
    ws = Path(workspace)
    kb_path = ws / "corpus" / "cad_knowledge.sqlite"
    out_dir = ws / "ops"
    summary = learn_from_kb(kb_path, out_dir=out_dir)
    return summary
