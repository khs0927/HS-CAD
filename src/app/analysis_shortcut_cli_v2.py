from __future__ import annotations

from pathlib import Path
from typing import Iterable

from src.app.cli import app


ANALYSIS_RUN_ALL = [
    "analysis_core_megapack",
    "analysis_graph_megapack",
    "analysis_advanced_megapack",
    "analysis_ops_megapack",
    "analysis_automation_megapack",
    "analysis_evidence_megapack",
    "analysis_export_megapack",
]


@app.command("hscad-analysis-run-all-v2")
def hscad_analysis_run_all_v2(
    workspace: str,
    dry_run: bool = True,
    create_zip: bool = False,
) -> None:
    """Print the full analysis worker sequence.

    This command is intentionally a shortcut scaffold. It prints the commands to run.
    Actual execution should remain in the worker runner until validation is complete.
    """
    for worker in ANALYSIS_RUN_ALL:
        suffix = ""
        if worker == "analysis_export_megapack" and create_zip:
            suffix = " --option create_zip=true"
        print(f"python -X utf8 -m src.main hscad-worker-run {worker} --workspace {workspace}{suffix}")


@app.command("hscad-analysis-export-plan")
def hscad_analysis_export_plan(workspace: str, create_zip: bool = False) -> None:
    """Print the export/packaging worker command."""
    suffix = " --option create_zip=true" if create_zip else ""
    print(f"python -X utf8 -m src.main hscad-worker-run analysis_export_megapack --workspace {workspace}{suffix}")


@app.command("hscad-analysis-open-dashboard")
def hscad_analysis_open_dashboard(workspace: str) -> None:
    """Print the expected validation dashboard path."""
    path = Path(workspace) / "VALIDATION_DASHBOARD.html"
    print(str(path))
