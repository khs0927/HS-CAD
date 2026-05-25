from __future__ import annotations

from src.app.cli import app
from src.analysis.pipeline_execution_reporter import (
    DEFAULT_FULL_SEQUENCE,
    REPORT_SEQUENCE,
    run_pipeline_sequence,
)


@app.command("hscad-analysis-run-all-exec")
def hscad_analysis_run_all_exec(
    workspace: str,
    dry_run: bool = True,
    stop_on_error: bool = True,
    timeout_sec: int = 1800,
) -> None:
    """Run or dry-run the full HS-CAD analysis worker sequence."""
    result = run_pipeline_sequence(
        workspace,
        sequence=DEFAULT_FULL_SEQUENCE,
        dry_run=dry_run,
        stop_on_error=stop_on_error,
        timeout_sec=timeout_sec,
    )
    print("status: ok")
    print(f"planned: {result['summary']['planned_count']}")
    print(f"errors: {result['summary']['error_count']}")
    print(f"report: {workspace}/pipeline_execution/PIPELINE_EXECUTION_REPORT.md")


@app.command("hscad-analysis-report-exec")
def hscad_analysis_report_exec(
    workspace: str,
    dry_run: bool = True,
    stop_on_error: bool = True,
    timeout_sec: int = 1800,
) -> None:
    """Run or dry-run only report/export/storage/evidence workers."""
    result = run_pipeline_sequence(
        workspace,
        sequence=REPORT_SEQUENCE,
        dry_run=dry_run,
        stop_on_error=stop_on_error,
        timeout_sec=timeout_sec,
    )
    print("status: ok")
    print(f"planned: {result['summary']['planned_count']}")
    print(f"errors: {result['summary']['error_count']}")
    print(f"report: {workspace}/pipeline_execution/PIPELINE_EXECUTION_REPORT.md")
