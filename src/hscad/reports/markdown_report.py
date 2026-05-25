"""Markdown report writer for review-only pipeline."""
from __future__ import annotations

from pathlib import Path
from typing import Any


def write_markdown_report(path: str | Path, result: dict[str, Any]) -> Path:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    drawing = result.get("drawing", {})
    fusion = result.get("fusion", {})
    rules = result.get("domain_rule_results", [])
    lines = [
        "# HS-CAD Main Code Pipeline Report",
        "",
        "## Input",
        f"- Path: `{drawing.get('input_path', '')}`",
        f"- Format: `{drawing.get('source_format', '')}`",
        f"- Entity count: `{len(drawing.get('entities', []))}`",
        "",
        "## Fusion Summary",
        f"- Evidence count: `{fusion.get('evidence_count', 0)}`",
        f"- Conflicts: `{len(fusion.get('conflicts', []))}`",
        "",
        "## Domain Rule Results",
    ]
    for rule in rules:
        lines.append(f"- **{rule.get('rule_id')}**: `{rule.get('status')}` / {rule.get('message')}")
    lines += ["", "## Safety", "- CAD execution: `false`", "- ZWCAD COM SendCommand: `false`", "- XiCAD alias execution: `false`", "- Original DWG mutation: `false`", ""]
    out.write_text("\n".join(lines), encoding="utf-8")
    return out
