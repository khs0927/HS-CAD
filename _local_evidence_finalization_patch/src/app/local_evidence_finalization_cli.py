from __future__ import annotations

import typer

from src.analysis.local_evidence_finalization_safety_spec_approval import write_local_evidence_finalization_outputs
from src.app.cli import app
from src.app.logger import console


@app.command("hscad-local-evidence-finalization")
def hscad_local_evidence_finalization(
    repo_root: str = typer.Option(".", help="Repository root."),
    out_dir: str = typer.Option("outputs/local_evidence_finalization_safety_spec_approval", help="Output directory."),
):
    """Finalize local validation evidence and prepare safety spec approval. Does not execute CAD."""

    result = write_local_evidence_finalization_outputs(repo_root=repo_root, out_dir=out_dir)
    console.print(result)
