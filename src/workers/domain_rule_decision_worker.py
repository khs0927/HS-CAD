from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.domain_rules.decision_engine import DomainRuleDecisionEngine
from src.domain_rules.decision_report import render_decision_markdown
from src.domain_rules.orchestrator import DomainRuleOrchestrator
from src.reports.json_exporter import export_json


def load_objects_json(path: str | Path) -> list[dict[str, Any]]:
    data = json.loads(Path(path).read_text(encoding='utf-8'))
    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]
    if isinstance(data, dict):
        for key in ('objects', 'entities', 'items'):
            value = data.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
    raise ValueError(f'Unsupported objects JSON shape: {path}')


def run_domain_rule_decision_worker(
    objects_json: str | Path,
    *,
    out_dir: str | Path = 'outputs/domain_rule_decision',
    task: str = 'drawing modification decision',
    xicad_root: str | Path = 'C:/xicad',
    archioffice_root: str | Path | None = None,
    hssteel_root: str | Path | None = None,
) -> dict[str, Any]:
    objects = load_objects_json(objects_json)
    orchestrator = DomainRuleOrchestrator(
        xicad_root=xicad_root,
        archioffice_root=archioffice_root,
        hssteel_root=hssteel_root,
    )
    engine = DomainRuleDecisionEngine(orchestrator)
    package = engine.decide(objects, task=task, source=str(objects_json))

    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    package_json = out / 'DOMAIN_RULE_DECISION_PACKAGE.json'
    report_md = out / 'DOMAIN_RULE_DECISION_PACKAGE.md'
    prompt_txt = out / 'SYSTEM_DRAFTING_CONSTRAINTS.txt'

    export_json(package.to_dict(), package_json)
    report_md.write_text(render_decision_markdown(package), encoding='utf-8')
    prompt_txt.write_text(package.system_prompt, encoding='utf-8')

    return {
        'objects_json': str(objects_json),
        'out_dir': str(out),
        'json': str(package_json),
        'report': str(report_md),
        'prompt': str(prompt_txt),
        'status': package.status,
        'decision_count': len(package.decisions),
        'warning_count': len(package.warnings),
    }
