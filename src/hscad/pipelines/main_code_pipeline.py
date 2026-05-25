"""HS-CAD main-code review pipeline.

This is the first real wiring layer after the architecture skeleton. It connects:
fileizers → analyzers → domain rules → fusion → DXF review outputs → SQLite index → report.

It is review-only. It does not execute CAD commands and never mutates original DWG files.
"""
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from hscad.analyzers.basic_entity_analyzer import BasicEntityAnalyzer
from hscad.cad.dxf_builders import ResultDxfBuilder
from hscad.core.jsonio import write_json
from hscad.domain_rules.runner import DomainRuleRunner
from hscad.fileizers.batch_fileizer import BatchFileizer
from hscad.fusion.evidence_fusion import EvidenceFusionEngine
from hscad.indexing.sqlite_store import SqliteEvidenceStore
from hscad.reports.markdown_report import write_markdown_report
from hscad.safety.policy import SAFETY_FLAGS, assert_safe_defaults


def run_main_code_pipeline(input_path: str | Path, out_dir: str | Path) -> dict[str, Any]:
    assert_safe_defaults()
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    drawing = BatchFileizer().fileize_one(input_path, out_dir=out / "converted")
    analysis = BasicEntityAnalyzer().analyze(drawing)
    rule_results = DomainRuleRunner().evaluate(drawing)

    all_evidence = []
    all_evidence.extend(drawing.evidence)
    all_evidence.extend(analysis.evidence)
    all_evidence.extend(r.as_evidence() for r in rule_results)

    fusion_engine = EvidenceFusionEngine()
    fusion = fusion_engine.fuse(all_evidence)
    fusion_paths = fusion_engine.write_outputs(out, fusion)

    qa_messages = [f"{c.get('type')}: {c.get('message')}" for c in fusion.conflicts]
    dxf_paths = ResultDxfBuilder().build_all(out, drawing.entities, qa_messages)

    index_path = out / "hscad_evidence.sqlite3"
    store = SqliteEvidenceStore(index_path)
    store.add_drawing(drawing, all_evidence)

    result: dict[str, Any] = {
        "input": str(input_path),
        "out_dir": str(out),
        "safety_flags": SAFETY_FLAGS,
        "drawing": drawing.to_record(),
        "analysis": analysis.to_record(),
        "domain_rule_results": [r.to_record() for r in rule_results],
        "fusion": fusion.to_record(),
        "fusion_outputs": fusion_paths,
        "dxf_review_outputs": dxf_paths,
        "sqlite_index": str(index_path),
        "sqlite_counts": store.counts(),
    }
    write_json(out / "FILEIZED_DRAWING.json", drawing.to_record())
    write_json(out / "ANALYSIS_GRAPH.json", analysis.to_record())
    write_json(out / "DOMAIN_RULE_RESULTS.json", [r.to_record() for r in rule_results])
    write_json(out / "MAIN_CODE_PIPELINE_RESULT.json", result)
    report_path = write_markdown_report(out / "FINAL_REPORT.md", result)
    result["final_report"] = str(report_path)
    write_json(out / "MAIN_CODE_PIPELINE_RESULT.json", result)
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run HS-CAD main-code review pipeline")
    parser.add_argument("--input", required=True, help="Input DWG/DXF/PDF/image path")
    parser.add_argument("--out", default="outputs/main_code_pipeline", help="Output directory")
    args = parser.parse_args(argv)
    result = run_main_code_pipeline(args.input, args.out)
    print(f"MAIN_CODE_PIPELINE_RESULT={result['out_dir']}/MAIN_CODE_PIPELINE_RESULT.json")
    print(f"FINAL_REPORT={result['final_report']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
