from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import typer

from src.corpus.corpus_learner import learn_from_kb
from src.corpus.corpus_query import format_query_result_markdown, query_kb
from src.corpus.fileized_ingest import ingest_fileized_folder
from src.corpus.report_builder import build_report

next_phase_app = typer.Typer(help="Next phase corpus commands for fileized ingestion, learning, query, and report.")


@next_phase_app.command("index-fileized")
def index_fileized(
    fileized: Path = typer.Option(..., help="outputs/fileized root or a single fileized JSON"),
    out: Path = typer.Option(Path("outputs/corpus"), help="Corpus output directory"),
    limit: Optional[int] = typer.Option(None, help="Limit number of JSON files to ingest"),
):
    """fileizer 결과 JSON을 cad_knowledge.sqlite에 인덱싱한다."""
    out.mkdir(parents=True, exist_ok=True)
    db_path = out / "cad_knowledge.sqlite"
    stats = ingest_fileized_folder(fileized, db_path, limit=limit)
    (out / "fileized_ingest_summary.json").write_text(json.dumps(stats, ensure_ascii=False, indent=2), encoding="utf-8")
    typer.echo(json.dumps(stats, ensure_ascii=False, indent=2))


@next_phase_app.command("learn")
def learn(
    kb: Path = typer.Option(..., help="cad_knowledge.sqlite path"),
    out: Path = typer.Option(Path("outputs/corpus"), help="Output directory"),
    top_n: int = typer.Option(20, help="Top N statistics"),
):
    """SQLite 지식베이스에서 통계와 architectural lesson을 생성한다."""
    summary = learn_from_kb(kb, out_dir=out, top_n=top_n)
    typer.echo(json.dumps(summary, ensure_ascii=False, indent=2))


@next_phase_app.command("query")
def query(
    kb: Path = typer.Option(..., help="cad_knowledge.sqlite path"),
    query_text: str = typer.Option(..., "--query", help="Natural language query"),
    company_profile: Optional[Path] = typer.Option(None, help="CompanyDraftingProfile JSON"),
    out: Optional[Path] = typer.Option(None, help="Optional markdown output path"),
):
    """Corpus를 검색하고 회사 기준 출력 추천을 함께 반환한다."""
    result = query_kb(kb, query_text, company_profile_path=company_profile)
    typer.echo(json.dumps(result, ensure_ascii=False, indent=2))
    if out:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(format_query_result_markdown(result), encoding="utf-8")


@next_phase_app.command("report")
def report(
    kb: Path = typer.Option(..., help="cad_knowledge.sqlite path"),
    out: Path = typer.Option(..., help="Markdown report path"),
    company_profile: Optional[Path] = typer.Option(None, help="CompanyDraftingProfile JSON"),
):
    """Corpus 통계와 lesson을 Markdown 리포트로 생성한다."""
    build_report(kb, out, company_profile_path=company_profile)
    typer.echo(f"Report written: {out}")
