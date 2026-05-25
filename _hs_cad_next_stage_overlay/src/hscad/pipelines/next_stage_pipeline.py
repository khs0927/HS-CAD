"""End-to-end next-stage smoke pipeline.

Usage:
  python -m hscad.pipelines.next_stage_pipeline --input path/to/file.dxf --out outputs/next_stage_smoke
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

SAFETY_FLAGS = {
    "final_live_runner_implemented": False,
    "sendcommand_allowed_by_default": False,
    "cad_execution_allowed_by_default": False,
    "zwcad_com_allowed_by_default": False,
    "xicad_alias_execution_allowed_by_default": False,
}


def run_next_stage_pipeline(input_path: str | Path, out_dir: str | Path) -> dict[str, Any]:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    drawing = BatchFileizer().fileize_one(input_path, out_dir=out / "converted")
    analysis = BasicEntityAnalyzer().analyze(drawing)
    rule_results = DomainRuleRunner().evaluate(drawing)

    all_evidence = []
    all_evidence.extend(drawing.evidence)
    all_evidence.extend(analysis.evidence)
    all_evidence.extend(result.as_evidence() for result in rule_results)

    fusion = EvidenceFusionEngine().fuse(all_evidence)
    fusion_paths = fusion.write_outputs(out)

    qa_messages = [
        f"{result.rule_id}: {result.recommended_action}"
        for result in rule_results
        if str(result.status) != "RuleStatus.PASS" and str(result.status) != "pass"
    ]
    dxf_plans = ResultDxfBuilder(out).build_all(drawing.entities, qa_messages)

    result = {
        "input": str(input_path),
        "out_dir": str(out),
        "safety_flags": SAFETY_FLAGS,
        "drawing": drawing.to_record(),
        "basic_entity_analysis": analysis.to_record(),
        "domain_rule_results": [item.to_record() for item in rule_results],
        "fusion_outputs": fusion_paths,
        "dxf_build_plans": [plan.to_record() for plan in dxf_plans],
    }
    write_json(out / "FILEIZED_DRAWING.json", drawing.to_record())
    write_json(out / "BASIC_ENTITY_ANALYSIS.json", analysis.to_record())
    write_json(out / "DOMAIN_RULE_RESULTS.json", [item.to_record() for item in rule_results])
    write_json(out / "NEXT_STAGE_PIPELINE_RESULT.json", result)
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run HS-CAD next-stage smoke pipeline")
    parser.add_argument("--input", required=True, help="Input DWG/DXF/PDF/image path")
    parser.add_argument("--out", default="outputs/next_stage_smoke", help="Output directory")
    args = parser.parse_args(argv)
    result = run_next_stage_pipeline(args.input, args.out)
    print(f"NEXT_STAGE_PIPELINE_RESULT={Path(result['out_dir']) / 'NEXT_STAGE_PIPELINE_RESULT.json'}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
