"""Bridge existing HS-CAD output artifacts into evidence/fusion outputs.

Review-only. No CAD execution. No COM. No DWG mutation.
"""
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from hscad.connectors.legacy_artifact_adapter import LegacyArtifactAdapter
from hscad.core.jsonio import write_json
from hscad.fusion.evidence_fusion import EvidenceFusionEngine
from hscad.indexing.sqlite_store import SqliteEvidenceStore
from hscad.reports.evidence_bridge_report import write_evidence_bridge_report
from hscad.safety.policy import SAFETY_FLAGS, assert_safe_defaults


def run_evidence_bridge_pipeline(legacy_dir: str | Path, out_dir: str | Path) -> dict[str, Any]:
    assert_safe_defaults()
    legacy = Path(legacy_dir)
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    adapter = LegacyArtifactAdapter()
    bridge = adapter.load(legacy)
    drawing = adapter.drawing_from_fileized_artifact(bridge)

    fusion_engine = EvidenceFusionEngine()
    fusion = fusion_engine.fuse(bridge.evidence)
    fusion_paths = fusion_engine.write_outputs(out, fusion)

    evidence_graph = {
        "source_dir": str(legacy),
        "artifact_count": len(bridge.artifacts),
        "evidence_count": len(bridge.evidence),
        "nodes": [e.to_record() for e in bridge.evidence],
        "edges": build_evidence_edges(bridge.to_record()),
    }

    index_path = out / "hscad_evidence_bridge.sqlite3"
    store = SqliteEvidenceStore(index_path)
    store.add_drawing(drawing, bridge.evidence)

    result: dict[str, Any] = {
        "legacy_dir": str(legacy),
        "out_dir": str(out),
        "safety_flags": SAFETY_FLAGS,
        "bridge": bridge.to_record(),
        "fusion": fusion.to_record(),
        "fusion_outputs": fusion_paths,
        "evidence_graph": evidence_graph,
        "sqlite_index": str(index_path),
        "sqlite_counts": store.counts(),
    }
    write_json(out / "LEGACY_ARTIFACT_BRIDGE_RESULT.json", bridge.to_record())
    write_json(out / "EVIDENCE_GRAPH.json", evidence_graph)
    write_json(out / "EVIDENCE_BRIDGE_PIPELINE_RESULT.json", result)
    report_path = write_evidence_bridge_report(out / "EVIDENCE_BRIDGE_REPORT.md", result)
    result["evidence_bridge_report"] = str(report_path)
    write_json(out / "EVIDENCE_BRIDGE_PIPELINE_RESULT.json", result)
    return result


def build_evidence_edges(bridge_record: dict[str, Any]) -> list[dict[str, Any]]:
    edges: list[dict[str, Any]] = []
    artifacts = bridge_record.get("artifacts", [])
    evidence = bridge_record.get("evidence", [])
    for artifact in artifacts:
        artifact_path = artifact.get("path")
        artifact_name = artifact.get("name")
        for item in evidence:
            source = item.get("source", {}) if isinstance(item, dict) else {}
            if source.get("source_id") == artifact_path:
                edges.append({"from": artifact_name, "to": item.get("evidence_id"), "relation": "emits"})
    return edges


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Bridge existing HS-CAD output artifacts into evidence/fusion outputs")
    parser.add_argument("--legacy-dir", required=True, help="Directory containing existing HS-CAD JSON artifacts")
    parser.add_argument("--out", default="outputs/evidence_bridge", help="Output directory")
    args = parser.parse_args(argv)
    result = run_evidence_bridge_pipeline(args.legacy_dir, args.out)
    print(f"EVIDENCE_BRIDGE_PIPELINE_RESULT={result['out_dir']}/EVIDENCE_BRIDGE_PIPELINE_RESULT.json")
    print(f"EVIDENCE_BRIDGE_REPORT={result['evidence_bridge_report']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
