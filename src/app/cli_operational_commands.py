"""Operational corpus commands for HS-CAD.

Add to the main Typer app with:

    from src.app.cli_operational_commands import corpus_ops_app
    app.add_typer(corpus_ops_app, name="corpus-ops")
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer

from src.corpus.evidence_pack import build_evidence_pack
from src.corpus.export_dataset import export_corpus_jsonl
from src.corpus.quality_audit import audit_corpus
from src.corpus.relationship_graph import build_relationship_graph

corpus_ops_app = typer.Typer(help="Operational corpus tools: evidence packs, graph, audit, export, output planning.")


@corpus_ops_app.command("audit")
def audit_command(
    kb: Path = typer.Option(..., "--kb", help="Path to cad_knowledge.sqlite"),
    out: Path = typer.Option(Path("outputs/corpus_ops"), "--out", help="Output directory"),
) -> None:
    report = audit_corpus(kb, out)
    typer.echo(f"Audit written to {out}")
    typer.echo(f"OK: {report.ok}")
    if report.warnings:
        typer.echo("Warnings:")
        for w in report.warnings:
            typer.echo(f"- {w}")


@corpus_ops_app.command("graph")
def graph_command(
    kb: Path = typer.Option(..., "--kb", help="Path to cad_knowledge.sqlite"),
    out: Path = typer.Option(Path("outputs/corpus_ops"), "--out", help="Output directory"),
) -> None:
    graph = build_relationship_graph(kb, out)
    typer.echo(f"Graph written to {out}")
    typer.echo(f"Nodes: {len(graph.nodes)}, Edges: {len(graph.edges)}")


@corpus_ops_app.command("query-pack")
def query_pack_command(
    kb: Path = typer.Option(..., "--kb", help="Path to cad_knowledge.sqlite"),
    query: str = typer.Option(..., "--query", help="Natural language query"),
    out: Path = typer.Option(Path("outputs/corpus_ops"), "--out", help="Output directory"),
    limit: int = typer.Option(30, "--limit", help="Max evidence hits"),
) -> None:
    pack = build_evidence_pack(kb, query=query, out_dir=out, limit=limit)
    typer.echo(f"Evidence pack written to {out}")
    typer.echo(f"Hits: {len(pack.hits)}, Confidence: {pack.confidence}")


@corpus_ops_app.command("export-jsonl")
def export_jsonl_command(
    kb: Path = typer.Option(..., "--kb", help="Path to cad_knowledge.sqlite"),
    out: Path = typer.Option(..., "--out", help="Output JSONL path"),
    include_paths: bool = typer.Option(False, "--include-paths", help="Include full source paths"),
) -> None:
    count = export_corpus_jsonl(kb, out, include_paths=include_paths)
    typer.echo(f"Exported {count} JSONL records to {out}")


@corpus_ops_app.command("plan-output")
def plan_output_command(
    evidence: Path = typer.Option(..., "--evidence", help="Path to evidence_pack.json"),
    company_profile: Path = typer.Option(..., "--company-profile", help="Path to company_drafting_profile.json"),
    out: Path = typer.Option(Path("outputs/corpus_ops"), "--out", help="Output directory"),
) -> None:
    from src.company_profile.company_output_planner import build_company_output_plan

    plan = build_company_output_plan(evidence, company_profile, out)
    typer.echo(f"Company output plan written to {out}")
    typer.echo(f"Titleblock: {plan.titleblock or 'unresolved'}")


@corpus_ops_app.command("run-operational-report")
def run_operational_report_command(
    kb: Path = typer.Option(..., "--kb", help="Path to cad_knowledge.sqlite"),
    query: str = typer.Option(..., "--query", help="Natural language query"),
    out: Path = typer.Option(Path("outputs/corpus_ops"), "--out", help="Output directory"),
    company_profile: Optional[Path] = typer.Option(None, "--company-profile", help="Optional company profile JSON"),
) -> None:
    audit_corpus(kb, out)
    build_relationship_graph(kb, out)
    pack = build_evidence_pack(kb, query=query, out_dir=out)
    export_corpus_jsonl(kb, out / "dataset.jsonl")
    if company_profile:
        from src.company_profile.company_output_planner import build_company_output_plan

        build_company_output_plan(out / "evidence_pack.json", company_profile, out)
    typer.echo(f"Operational report artifacts written to {out}")
    typer.echo(f"Evidence hits: {len(pack.hits)}")
