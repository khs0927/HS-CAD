from __future__ import annotations

from pathlib import Path

import typer

from src.app.cli import app
from src.app.logger import console, success
from src.domain_rules.orchestrator import DomainRuleOrchestrator
from src.domain_rules.prompt_builder import build_review_markdown, build_system_drafting_constraints
from src.reports.json_exporter import export_json


@app.command('domain-rule-pack')
def domain_rule_pack(
    xicad_root: str = typer.Option('C:/xicad', help='XiCAD root path'),
    archioffice_root: str | None = typer.Option(None, help='Optional ArchiOffice root path'),
    hssteel_root: str | None = typer.Option(None, help='Optional HS-Steel root path'),
    out: str | None = typer.Option(None, help='Optional JSON output path'),
):
    orchestrator = DomainRuleOrchestrator(
        xicad_root=xicad_root,
        archioffice_root=archioffice_root,
        hssteel_root=hssteel_root,
    )
    packs = orchestrator.build_knowledge_packs()
    payload = [pack.to_dict() for pack in packs]
    if out:
        export_json(payload, out)
        success(f'Domain rule pack written: {out}')
    else:
        console.print(payload)


@app.command('domain-rule-review-synthetic')
def domain_rule_review_synthetic(
    xicad_root: str = typer.Option('C:/xicad', help='XiCAD root path'),
    out_dir: str = typer.Option('outputs/domain_rule_review_synthetic', help='Output directory'),
):
    objects = [
        {'object_name': 'AcDbPolyline', 'entity_type': 'POLYLINE', 'closed': True, 'layer': 'WAL1'},
        {'object_name': 'AcDbBlockReference', 'entity_type': 'INSERT', 'layer': '0', 'name': 'H-300x150'},
        {'object_name': 'AcDbText', 'entity_type': 'TEXT', 'layer': 'ROOM-TEXT', 'text': 'ROOM 101'},
    ]
    orchestrator = DomainRuleOrchestrator(xicad_root=xicad_root)
    packs = orchestrator.build_knowledge_packs()
    review = orchestrator.review_drawing(objects, task='synthetic modification review')
    prompt = build_system_drafting_constraints(packs, review)

    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    review_json = out / 'DOMAIN_RULE_REVIEW.json'
    prompt_txt = out / 'SYSTEM_DRAFTING_CONSTRAINTS.txt'
    report_md = out / 'DOMAIN_RULE_REVIEW.md'
    export_json(review.to_dict(), review_json)
    prompt_txt.write_text(prompt, encoding='utf-8')
    report_md.write_text(build_review_markdown(review, prompt=prompt), encoding='utf-8')
    success(f'Domain rule review written: {review_json}')
    success(f'Drafting constraints prompt written: {prompt_txt}')
    success(f'Domain rule report written: {report_md}')
