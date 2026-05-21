from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from image_to_cad.auto.active_analyzer import ActiveDrawingAnalysis
from image_to_cad.auto.live_preview import PreviewResult


def write_auto_analysis(
    analysis: ActiveDrawingAnalysis,
    out_dir: str | Path,
    preview_result: PreviewResult | None = None,
) -> dict[str, str]:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    inventory_path = out / "auto_inventory.json"
    candidates_path = out / "layer_mapping_candidates.csv"
    plan_path = out / "auto_preview_plan.json"
    result_path = out / "auto_preview_result.json"
    report_path = out / "auto_analysis_report.md"

    inventory = analysis.to_dict()
    inventory_path.write_text(json.dumps(inventory, ensure_ascii=False, indent=2, default=str), encoding="utf-8")

    candidate_rows = [candidate.to_dict() for candidate in analysis.candidates]
    with candidates_path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=list(candidate_rows[0].keys()) if candidate_rows else ["empty"])
        writer.writeheader()
        writer.writerows(candidate_rows)

    plan = {
        "mode": "live_preview_plan_no_save",
        "active_doc": analysis.active_doc,
        "candidate_count": len(candidate_rows),
        "default_applicable_count": sum(1 for row in candidate_rows if row["apply_by_default"]),
        "layer_zero_default_blocked": True,
        "forbidden_operations": ["Save", "SaveAs", "Purge", "Delete", "Explode", "BlockDefinitionEdit", "RawCommand"],
        "undo": "UNDO MARK before preview; UNDO BACK to restore",
        "candidates": candidate_rows,
    }
    plan_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2, default=str), encoding="utf-8")

    if preview_result is not None:
        result_path.write_text(json.dumps(preview_result.to_dict(), ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    elif not result_path.exists():
        result_path.write_text(json.dumps({"status": "not_applied"}, ensure_ascii=False, indent=2), encoding="utf-8")

    report_path.write_text(_markdown_report(analysis, preview_result), encoding="utf-8")
    return {
        "inventory": str(inventory_path),
        "candidates": str(candidates_path),
        "plan": str(plan_path),
        "preview_result": str(result_path),
        "report": str(report_path),
    }


def _markdown_report(analysis: ActiveDrawingAnalysis, preview_result: PreviewResult | None) -> str:
    lines = [
        "# Auto Analysis Live Preview Report",
        "",
        f"- Generated: {analysis.generated_at}",
        f"- Active DWG: {analysis.active_doc}",
        f"- Object count: {analysis.object_count}",
        f"- Layer count: {len(analysis.layer_counts)}",
        f"- Dimension count: {analysis.dimension_count}",
        f"- Candidate count: {len(analysis.candidates)}",
        "",
        "## Safety",
        "- Save/SaveAs: forbidden",
        "- Purge/Delete/Explode: forbidden",
        "- Block definition edits: forbidden",
        "- Layer 0: blocked by default",
        "- Preview restore: UNDO BACK",
        "",
        "## Mapping Candidates",
        "| Source | Target | Count | Confidence | Default | Reason |",
        "|---|---|---:|---:|---|---|",
    ]
    for candidate in sorted(analysis.candidates, key=lambda item: (-item.object_count, item.source_layer.upper()))[:120]:
        lines.append(
            f"| {candidate.source_layer} | {candidate.target_layer or ''} | {candidate.object_count} | "
            f"{candidate.confidence:.2f} | {candidate.apply_by_default} | {candidate.reason or candidate.blocked_reason} |"
        )
    if preview_result:
        lines += [
            "",
            "## Preview Result",
            f"- Changed: {preview_result.changed}",
            f"- Skipped: {preview_result.skipped}",
            f"- Undo mark created: {preview_result.undo_mark_created}",
            f"- Errors: {len(preview_result.errors)}",
        ]
    return "\n".join(lines) + "\n"
