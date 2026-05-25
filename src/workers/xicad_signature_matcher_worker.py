from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.execution.xicad_signature_matcher import match_signatures_in_objects
from src.reports.json_exporter import export_json


def render_signature_matches_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# HS-CAD XiCAD Signature Matches",
        "",
        f"- Status: `{payload.get('status')}`",
        f"- Object count: `{payload.get('object_count')}`",
        f"- Signature count: `{payload.get('signature_count')}`",
        f"- Match count: `{payload.get('match_count')}`",
        "",
        "## Matches",
        "",
    ]
    for match in payload.get("matches") or []:
        lines.append(
            f"- `{match.get('alias')}` | {match.get('status')} | "
            f"confidence={match.get('confidence')} | handles={match.get('entity_handles')}"
        )
    lines += [
        "",
        "## Warnings",
        "",
    ]
    for warning in payload.get("warnings") or []:
        lines.append(f"- {warning}")
    lines += [
        "",
        "## Safety",
        "",
        "- This worker reads scan/signature JSON only.",
        "- This worker does not open ZWCAD.",
        "- This worker does not mutate CAD files.",
        "- All matches require human review before downstream use.",
        "",
    ]
    return "\n".join(lines)


def run_signature_matcher_worker(
    *,
    snapshot_json: str | Path,
    signatures_json: str | Path,
    out_dir: str | Path = "outputs/xicad_signature_matches",
) -> dict[str, Any]:
    with open(snapshot_json, "r", encoding="utf-8") as f:
        snapshot_data = json.load(f)
    with open(signatures_json, "r", encoding="utf-8") as f:
        signature_data = json.load(f)

    signatures = (
        signature_data.get("verified_signatures")
        or signature_data.get("signatures")
        or signature_data.get("seeds")
        or []
    )
    payload = match_signatures_in_objects(snapshot_data.get("objects") or [], signatures)

    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    matches_json = out / "XICAD_SIGNATURE_MATCHES.json"
    report_md = out / "XICAD_SIGNATURE_MATCHES.md"
    export_json(payload, matches_json)
    report_md.write_text(render_signature_matches_markdown(payload), encoding="utf-8")

    return {
        "status": payload["status"],
        "match_count": payload["match_count"],
        "matches_json": str(matches_json),
        "report": str(report_md),
    }
