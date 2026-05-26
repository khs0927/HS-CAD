from __future__ import annotations

from pathlib import Path
from typing import Any

from src.remote_worker.job_schema import RemoteDxfJob


def write_change_report(job: RemoteDxfJob, output_dir: str | Path, changes: list[str], inspection: dict[str, Any]) -> Path:
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    lines = [
        "# HS-CAD Remote DXF Worker Report",
        "",
        f"- Job ID: `{job.job_id}`",
        f"- Source type: `{job.source.type}`",
        f"- Source file: `{job.source.file_path or job.source.file_name or job.source.file_id or 'blank demo'}`",
        "",
        "## Changes",
    ]
    lines.extend(f"- {change}" for change in changes)
    lines.extend(["", "## Entity counts"])
    for key, value in inspection.get("entity_counts", {}).items():
        lines.append(f"- {key}: {value}")
    lines.extend(["", "## Layer counts"])
    for key, value in inspection.get("layer_counts", {}).items():
        lines.append(f"- {key}: {value}")
    path = out_dir / "change_report.md"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path
