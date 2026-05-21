"""Active drawing consolidated report.

Combines the probe information, dynamic block report and any XiCAD/LISP
preview data into a single JSON/Markdown document under ``generated/reports``.
"""

from __future__ import annotations

import json
from pathlib import Path

from .active_document_probe import write_active_probe_json, write_active_probe_md
from .dynamic_block_report import collect_dynamic_blocks, write_dynamic_block_report_json, write_dynamic_block_report_md


def generate_active_drawing_report(out_dir: str) -> dict[str, str]:
    """Generate both JSON and Markdown reports and return their absolute paths."""
    base = Path(out_dir)
    base.mkdir(parents=True, exist_ok=True)
    # Probe
    json_probe = write_active_probe_json(str(base / "active_probe.json"))
    md_probe = write_active_probe_md(str(base / "active_probe.md"))
    # Dynamic block report
    json_blocks = write_dynamic_block_report_json(str(base / "dynamic_block_report.json"))
    md_blocks = write_dynamic_block_report_md(str(base / "dynamic_block_report.md"))
    # Aggregate summary JSON for convenience
    summary = {
        "probe_json": json_probe,
        "probe_md": md_probe,
        "dynamic_blocks_json": json_blocks,
        "dynamic_blocks_md": md_blocks,
    }
    summary_path = base / "active_drawing_report.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return {
        "summary_json": str(summary_path),
        "probe_json": json_probe,
        "probe_md": md_probe,
        "dynamic_blocks_json": json_blocks,
        "dynamic_blocks_md": md_blocks,
    }
