from __future__ import annotations

from pathlib import Path
from typing import Any
import json

from .xicad_contracts import read_evidence
from .xicad_contract_validator import validate_contract_evidence


def find_record_files(records_dir: str | Path) -> list[Path]:
    root = Path(records_dir)
    if not root.exists():
        return []
    return sorted(root.glob("*_record.json")) + sorted(root.glob("contract_record*.json"))


def validate_contract_bundle(records_dir: str | Path, out_dir: str | Path) -> dict[str, str]:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, Any]] = []

    for path in find_record_files(records_dir):
        try:
            evidence = read_evidence(path)
            result = validate_contract_evidence(evidence, evidence_path=path)
            payload = result.to_dict()
            payload["record_path"] = str(path)
            rows.append(payload)
        except Exception as exc:
            rows.append({"record_path": str(path), "status": "ERROR", "can_promote": False, "error": str(exc)})

    summary = {
        "record_count": len(rows),
        "promotable_count": sum(1 for row in rows if row.get("can_promote")),
        "blocked_count": sum(1 for row in rows if not row.get("can_promote")),
        "records": rows,
    }

    json_path = out / "xicad_contract_bundle_validation.json"
    md_path = out / "xicad_contract_bundle_validation.md"
    json_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "# XiCAD Contract Bundle Validation",
        "",
        f"- Record count: {summary['record_count']}",
        f"- Promotable count: {summary['promotable_count']}",
        f"- Blocked count: {summary['blocked_count']}",
        "",
        "| Alias | Status | Can Promote | Missing | Record |",
        "|---|---|---|---|---|",
    ]
    for row in rows:
        lines.append(
            f"| {row.get('alias', '')} | {row.get('status', '')} | {row.get('can_promote', False)} | "
            f"{', '.join(row.get('missing', [])) if isinstance(row.get('missing'), list) else ''} | {row.get('record_path', '')} |"
        )
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {"json": str(json_path), "markdown": str(md_path)}
