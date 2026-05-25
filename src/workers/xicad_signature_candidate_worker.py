from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.execution.entity_delta import build_entity_delta
from src.execution.xicad_signature_candidate import build_signature_candidate
from src.reports.json_exporter import export_json


def load_snapshot_objects(path: str | Path) -> list[dict[str, Any]]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(data, dict) and isinstance(data.get("objects"), list):
        return [item for item in data["objects"] if isinstance(item, dict)]
    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]
    raise ValueError(f"Snapshot must be a JSON object with objects[] or a JSON list: {path}")


def render_signature_candidate_markdown(candidate: dict[str, Any], delta: dict[str, Any]) -> str:
    summary = delta.get("summary", {}) or {}
    lines = [
        "# HS-CAD XiCAD Signature Candidate",
        "",
        f"- Alias: `{candidate.get('alias')}`",
        f"- Status: `{candidate.get('status')}`",
        f"- Confidence: `{candidate.get('confidence')}`",
        f"- Requires human review: `{candidate.get('requires_human_review')}`",
        "",
        "## Entity Delta",
        "",
        f"- Before count: `{summary.get('before_count')}`",
        f"- After count: `{summary.get('after_count')}`",
        f"- Added: `{summary.get('added_count')}`",
        f"- Removed: `{summary.get('removed_count')}`",
        f"- Changed: `{summary.get('changed_count')}`",
        f"- Unchanged: `{summary.get('unchanged_count')}`",
        "",
        "## Geometry Patterns",
        "",
    ]

    patterns = candidate.get("geometry_patterns") or []
    if not patterns:
        lines.append("- No geometry pattern candidates detected.")
    else:
        for pattern in patterns:
            lines.append(f"- {pattern.get('kind')}: `{pattern.get('count')}`")

    lines += [
        "",
        "## Safety",
        "",
        "- This worker does not open ZWCAD.",
        "- This worker does not run SendCommand.",
        "- This worker does not modify CAD files.",
        "- Candidate signatures are not promoted to config automatically.",
        "",
    ]
    return "\n".join(lines)


def run_xicad_signature_candidate_worker(
    *,
    alias: str,
    before_snapshot_json: str | Path,
    after_snapshot_json: str | Path,
    out_dir: str | Path = "outputs/xicad_signature_candidate",
) -> dict[str, Any]:
    before_objects = load_snapshot_objects(before_snapshot_json)
    after_objects = load_snapshot_objects(after_snapshot_json)

    delta = build_entity_delta(before_objects, after_objects)
    candidate = build_signature_candidate(alias, delta, source="snapshot_delta")

    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    delta_json = out / "ENTITY_DELTA.json"
    candidate_json = out / "XICAD_SIGNATURE_CANDIDATE.json"
    report_md = out / "XICAD_SIGNATURE_CANDIDATE.md"

    delta_payload = delta.to_dict()
    candidate_payload = candidate.to_dict()

    export_json(delta_payload, delta_json)
    export_json(candidate_payload, candidate_json)
    report_md.write_text(
        render_signature_candidate_markdown(candidate_payload, delta_payload),
        encoding="utf-8",
    )

    return {
        "out_dir": str(out),
        "entity_delta": str(delta_json),
        "signature_candidate": str(candidate_json),
        "report": str(report_md),
        "alias": candidate.alias,
        "status": candidate.status,
        "requires_human_review": candidate.requires_human_review,
        "geometry_pattern_count": len(candidate.geometry_patterns),
        "added_count": delta.summary["added_count"],
        "changed_count": delta.summary["changed_count"],
        "removed_count": delta.summary["removed_count"],
    }
