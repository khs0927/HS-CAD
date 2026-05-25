from __future__ import annotations

from pathlib import Path

from src.app.cli import app


FULL_SEQUENCE_V3 = [
    "analysis_core_megapack",
    "analysis_graph_megapack",
    "analysis_advanced_megapack",
    "analysis_ops_megapack",
    "analysis_automation_megapack",
    "analysis_evidence_megapack",
    "analysis_export_megapack",
    "analysis_storage_megapack",
    "analysis_report_megapack",
]


@app.command("hscad-analysis-run-all-v3")
def hscad_analysis_run_all_v3(workspace: str, print_only: bool = True) -> None:
    """Print the full v3 analysis sequence."""
    for worker in FULL_SEQUENCE_V3:
        print(f"python -X utf8 -m src.main hscad-worker-run {worker} --workspace {workspace}")


@app.command("hscad-analysis-report-plan")
def hscad_analysis_report_plan(workspace: str) -> None:
    """Print report-stage worker commands."""
    for worker in ["analysis_evidence_megapack", "analysis_export_megapack", "analysis_storage_megapack", "analysis_report_megapack"]:
        print(f"python -X utf8 -m src.main hscad-worker-run {worker} --workspace {workspace}")


@app.command("hscad-analysis-redaction-plan")
def hscad_analysis_redaction_plan(workspace: str) -> None:
    """Print expected report redaction artifact path."""
    print(str(Path(workspace) / "REPORT_REDACTION_PLAN.md"))
