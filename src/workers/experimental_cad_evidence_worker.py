from __future__ import annotations

from pathlib import Path
from typing import Any

from src.adapters.ezdxf_adapter import EzDxfAdapter
from src.reports.evidence_report import render_evidence_markdown
from src.reports.json_exporter import export_json
from src.scanners.object_scanner import build_evidence_package


def run_ezdxf_evidence_worker(source: str | Path, out_dir: str | Path = 'outputs/experimental_cad_evidence') -> dict[str, Any]:
    source_path = Path(source)
    output_dir = Path(out_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    rows = EzDxfAdapter().read_dxf_entities(source_path)
    package = build_evidence_package(rows, source=str(source_path))

    json_path = output_dir / 'EXPERIMENTAL_CAD_EVIDENCE.json'
    report_path = output_dir / 'EXPERIMENTAL_CAD_EVIDENCE.md'
    export_json(package, json_path)
    report_path.write_text(render_evidence_markdown(package), encoding='utf-8')

    return {
        'source': str(source_path),
        'out_dir': str(output_dir),
        'json': str(json_path),
        'report': str(report_path),
        'object_count': package.get('object_count', 0),
        'boundary_count': package.get('boundary_summary', {}).get('candidate_count', 0),
        'dimension_count': package.get('dimension_summary', {}).get('dimension_count', 0),
    }
