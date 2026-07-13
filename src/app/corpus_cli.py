from __future__ import annotations

import os
from pathlib import Path

import typer

from src.app.cli import app
from src.app.logger import console, success
from src.corpus.quality import CorpusQualityAuditor
from src.corpus.validator import FileizedRecordValidator
from src.corpus_run.pipeline_runner import CorpusPipelineRunner
from src.drawing_index.application.run_service import DrawingIndexRunService
from src.drawing_index.infrastructure.local_sqlite_summary_sink import (
    LocalSQLiteRunSummarySink,
)
from src.drawing_index.infrastructure.supabase_summary_sink import SupabaseRunSummarySink

corpus_app = typer.Typer(help="HS-CAD corpus pipeline commands")
app.add_typer(corpus_app, name="corpus-run")


@corpus_app.command("prepare")
def corpus_prepare(
    root: Path = typer.Option(..., "--root"),
    workspace: Path = typer.Option(Path("outputs/corpus_workspace"), "--workspace"),
    sample: int = typer.Option(0, "--sample"),
):
    result = CorpusPipelineRunner(workspace).prepare(root, sample=sample)
    console.print(result)
    success("Corpus manifest prepared")


@corpus_app.command("fileize")
def corpus_fileize(
    workspace: Path = typer.Option(Path("outputs/corpus_workspace"), "--workspace"),
    limit: int = typer.Option(0, "--limit"),
):
    result = CorpusPipelineRunner(workspace).fileize(limit=limit)
    console.print(result)
    success("Corpus fileize stage complete")


def _enabled(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _summary_sink(workspace: Path, backend: str, cloud_summary: bool):
    selected = "supabase" if cloud_summary else backend.strip().lower()
    if selected == "local":
        return LocalSQLiteRunSummarySink(workspace / "drawing_index_history.sqlite")
    if selected == "none":
        return None
    if selected == "supabase":
        if not _enabled("HSCAD_ALLOW_EXTERNAL_SUMMARY"):
            raise typer.BadParameter(
                "External summaries are disabled by the free-local profile. Set "
                "HSCAD_ALLOW_EXTERNAL_SUMMARY=1 only when explicitly using a "
                "Supabase free-tier project."
            )
        sink = SupabaseRunSummarySink.from_env()
        if sink is None:
            raise typer.BadParameter(
                "Set HSCAD_SUPABASE_URL and HSCAD_SUPABASE_SERVICE_ROLE_KEY "
                "in a trusted environment before selecting the optional Supabase backend."
            )
        return sink
    raise typer.BadParameter("--summary-backend must be local, none, or supabase")


@corpus_app.command("complete")
def corpus_complete(
    root: Path = typer.Option(..., "--root"),
    workspace: Path = typer.Option(Path("outputs/corpus_workspace"), "--workspace"),
    sample: int = typer.Option(0, "--sample"),
    limit: int = typer.Option(0, "--limit"),
    summary_backend: str = typer.Option(
        os.getenv("HSCAD_SUMMARY_BACKEND", "local"),
        "--summary-backend",
        help=(
            "Run-summary destination: local (default, free/offline), none, or "
            "supabase (optional free-tier control plane)."
        ),
    ),
    cloud_summary: bool = typer.Option(
        False,
        "--cloud-summary/--no-cloud-summary",
        help="Legacy alias that selects the optional Supabase summary backend.",
    ),
):
    sink = _summary_sink(workspace, summary_backend, cloud_summary)
    result = DrawingIndexRunService(workspace, sink=sink).run(
        root,
        sample=sample,
        limit=limit,
    )
    console.print(result)
    if result["review_count"]:
        console.print(
            "[yellow]The run completed with REVIEW items. Open "
            "DRAWING_INDEX_RUN_SUMMARY.json before describing the index as complete.[/yellow]"
        )
        raise typer.Exit(code=1)
    success("Complete drawing index run finished")


@corpus_app.command("validate")
def corpus_validate(
    workspace: Path = typer.Option(Path("outputs/corpus_workspace"), "--workspace"),
):
    json_dir = workspace / "fileized" / "json"
    result = FileizedRecordValidator().validate_json_dir(json_dir)
    console.print(result)
    if result["invalid_count"]:
        raise typer.Exit(code=1)
    success("Corpus fileized JSON validation complete")


@corpus_app.command("index")
def corpus_index(
    workspace: Path = typer.Option(Path("outputs/corpus_workspace"), "--workspace"),
):
    result = CorpusPipelineRunner(workspace).index()
    console.print(result)
    success("Corpus index stage complete")


@corpus_app.command("learn")
def corpus_learn(
    workspace: Path = typer.Option(Path("outputs/corpus_workspace"), "--workspace"),
    out: Path | None = typer.Option(None, "--out"),
):
    result = CorpusPipelineRunner(workspace).learn(out)
    console.print(result)
    success("Corpus learn stage complete")


@corpus_app.command("query")
def corpus_query(
    text: str = typer.Argument(...),
    workspace: Path = typer.Option(Path("outputs/corpus_workspace"), "--workspace"),
    limit: int = typer.Option(20, "--limit"),
):
    console.print(CorpusPipelineRunner(workspace).query(text, limit=limit))


@corpus_app.command("evidence")
def corpus_evidence(
    text: str = typer.Argument(...),
    workspace: Path = typer.Option(Path("outputs/corpus_workspace"), "--workspace"),
    limit: int = typer.Option(20, "--limit"),
):
    console.print(CorpusPipelineRunner(workspace).evidence(text, limit=limit))


@corpus_app.command("quality")
def corpus_quality(
    workspace: Path = typer.Option(Path("outputs/corpus_workspace"), "--workspace"),
):
    auditor = CorpusQualityAuditor(workspace)
    result = {"json": auditor.write_json(), "markdown": auditor.write_markdown()}
    console.print(result)
    success("Corpus quality audit written")


@corpus_app.command("report")
def corpus_report(
    workspace: Path = typer.Option(Path("outputs/corpus_workspace"), "--workspace"),
    out: Path | None = typer.Option(None, "--out"),
):
    result = CorpusPipelineRunner(workspace).report(out)
    console.print(result)
    success("Corpus report written")
