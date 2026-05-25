"""Markdown report for the legacy-artifact evidence bridge."""
from __future__ import annotations

from pathlib import Path
from typing import Any


def write_evidence_bridge_report(path: str | Path, result: dict[str, Any]) -> Path:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    bridge = result.get("bridge", {})
    fusion = result.get("fusion", {})
    sqlite_counts = result.get("sqlite_counts", {})
    lines = [
        "# HS-CAD Evidence Bridge Report",
        "",
        "## Purpose",
        "This report bridges existing HS-CAD analyzer/exporter JSON artifacts into the new evidence/fusion model.",
        "It is review-only and does not execute CAD commands.",
        "",
        "## Source",
        f"- Legacy artifact directory: `{bridge.get('source_dir', '')}`",
        f"- Artifacts loaded: `{bridge.get('artifact_count', 0)}`",
        f"- Evidence emitted: `{bridge.get('evidence_count', 0)}`",
        "",
        "## Artifacts",
    ]
    for artifact in bridge.get("artifacts", []):
        lines.append(f"- `{artifact.get('name')}` → `{artifact.get('kind')}`")
    lines += [
        "",
        "## Fusion",
        f"- Evidence count: `{fusion.get('evidence_count', 0)}`",
        f"- Conflict count: `{len(fusion.get('conflicts', []))}`",
        "",
        "### Evidence by kind",
    ]
    for kind, count in sorted((fusion.get("by_kind") or {}).items()):
        lines.append(f"- `{kind}`: `{count}`")
    lines += ["", "### Recommendations"]
    for rec in fusion.get("recommendations", []):
        lines.append(f"- **{rec.get('priority', 'P?')}** `{rec.get('action', '')}` — {rec.get('details', '')}")
    lines += [
        "",
        "## SQLite Index",
        f"- Drawings: `{sqlite_counts.get('drawings', 0)}`",
        f"- Entities: `{sqlite_counts.get('entities', 0)}`",
        f"- Evidence: `{sqlite_counts.get('evidence', 0)}`",
        "",
        "## Safety",
        "- CAD execution: `false`",
        "- ZWCAD COM SendCommand: `false`",
        "- XiCAD alias execution: `false`",
        "- Original DWG mutation: `false`",
        "",
    ]
    out.write_text("\n".join(lines), encoding="utf-8")
    return out
