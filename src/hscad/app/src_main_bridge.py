"""Bridge helpers for optional `src.main` integration."""
from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Any


def dispatch_if_main_code_command(argv: Sequence[str] | None = None) -> int | None:
    import sys
    tokens = list(sys.argv[1:] if argv is None else argv)
    if not tokens or tokens[0] != "hscad-main-code-pipeline":
        return None
    from hscad.pipelines.main_code_pipeline import main as pipeline_main
    return pipeline_main(tokens[1:])


def register_main_code_command(app: Any) -> None:
    """Register a review-only Typer command without enabling CAD execution."""
    import typer

    @app.command("hscad-main-code-pipeline")
    def hscad_main_code_pipeline(
        input: Path = typer.Option(..., "--input", exists=True, readable=True),
        out: Path = typer.Option(Path("outputs/main_code_pipeline"), "--out"),
    ) -> None:
        from hscad.pipelines.main_code_pipeline import run_main_code_pipeline

        result = run_main_code_pipeline(input, out)
        typer.echo(f"MAIN_CODE_PIPELINE_RESULT={result['out_dir']}/MAIN_CODE_PIPELINE_RESULT.json")
        typer.echo(f"FINAL_REPORT={result['final_report']}")
