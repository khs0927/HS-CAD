from __future__ import annotations

import typer

from src.analysis.post_pr53_main_merge_local_validation import write_post_pr53_outputs
from src.app.cli import app
from src.app.logger import console


@app.command("hscad-post-pr53-main-readiness")
def hscad_post_pr53_main_readiness(
    repo_root: str = typer.Option(".", help="Repository root."),
    main_readiness_workspace: str = typer.Option("outputs/main_readiness_local_validation", help="Workspace containing PR53 main readiness artifacts."),
    out_dir: str = typer.Option("outputs/post_pr53_main_merge_local_validation", help="Output directory."),
):
    """Generate Post-PR53 main merge and local-only validation planning artifacts."""

    result = write_post_pr53_outputs(
        repo_root=repo_root,
        main_readiness_workspace=main_readiness_workspace,
        out_dir=out_dir,
    )
    console.print(result)
