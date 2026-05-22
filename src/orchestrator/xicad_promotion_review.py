from __future__ import annotations

from pathlib import Path
from typing import Any
import json

from .xicad_contract_bundle import find_record_files
from .xicad_contracts import read_evidence
from .xicad_contract_validator import validate_contract_evidence


def build_promotion_review_pack(records_dir: str | Path, out_dir: str | Path) -> dict[str, str]:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    candidates: list[dict[str, Any]] = []
    blocked: list[dict[str, Any]] = []

    for record_path in find_record_files(records_dir):
        evidence = read_evidence(record_path)
        result = validate_contract_evidence(evidence, evidence_path=record_path)
        if result.can_promote and result.promotion_candidate:
            candidate = dict(result.promotion_candidate)
            candidate["record_path"] = str(record_path)
            candidates.append(candidate)
        else:
            blocked.append({"record_path": str(record_path), "alias": result.alias, "missing": result.missing, "status": result.status})

    payload = {
        "mode": "human_review_required",
        "auto_modify_recipe_registry": False,
        "candidate_count": len(candidates),
        "blocked_count": len(blocked),
        "candidates": candidates,
        "blocked": blocked,
        "review_instructions": [
            "Open each record_path and confirm the manual observation.",
            "Do not promote if the command caused Save/Delete/Explode/Purge side effects.",
            "If approved, update xicad_recipe_registry.py manually in a separate commit.",
            "Keep auto_run_allowed=False unless a later Safe Bridge preview flow is implemented.",
        ],
    }

    json_path = out / "xicad_promotion_review_pack.json"
    md_path = out / "xicad_promotion_review_pack.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "# XiCAD Promotion Review Pack",
        "",
        f"- Candidate count: {len(candidates)}",
        f"- Blocked count: {len(blocked)}",
        "- Auto modify recipe registry: False",
        "",
        "## Candidates",
        "| Alias | Function | Scriptable | AutoRun | Evidence |",
        "|---|---|---|---|---|",
    ]
    for c in candidates:
        lines.append(f"| {c.get('alias')} | {c.get('function')} | {c.get('scriptable')} | {c.get('auto_run_allowed')} | {c.get('record_path')} |")
    lines += ["", "## Blocked"]
    for b in blocked:
        lines.append(f"- {b.get('alias')}: missing {', '.join(b.get('missing', []))}")
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {"json": str(json_path), "markdown": str(md_path)}
