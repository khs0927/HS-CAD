"""Optional Typer bridge for registering the evidence bridge command in src.main.

This module is safe to import. It only registers a review-only command when the
local repository chooses to patch src/main.py through the accompanying dry-run
script.
"""
from __future__ import annotations

from pathlib import Path

try:
    import typer
except Exception:  # pragma: no cover - Typer is present in the real app, optional in isolated smoke tests.
    typer = None  # type: ignore


def register_evidence_bridge_command(app) -> None:
    if typer is None:
        return

    @app.command("hscad-evidence-bridge")
    def hscad_evidence_bridge(
        legacy_dir: str = typer.Option(..., "--legacy-dir", help="Directory containing existing HS-CAD JSON artifacts"),
        out: str = typer.Option("outputs/evidence_bridge", "--out", help="Output directory"),
    ) -> None:
        from hscad.pipelines.evidence_bridge_pipeline import run_evidence_bridge_pipeline

        result = run_evidence_bridge_pipeline(Path(legacy_dir), Path(out))
        typer.echo(f"EVIDENCE_BRIDGE_PIPELINE_RESULT={result['out_dir']}/EVIDENCE_BRIDGE_PIPELINE_RESULT.json")
        typer.echo(f"EVIDENCE_BRIDGE_REPORT={result['evidence_bridge_report']}")
