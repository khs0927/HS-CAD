from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ExportPaths:
    out_dir: Path
    result_json: Path
    qa_report: Path
    overlay: Path
    centerline_dxf: Path
    wallsolid_dxf: Path


def build_export_paths(out_dir: str | Path) -> ExportPaths:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    return ExportPaths(
        out_dir=out,
        result_json=out / "result.json",
        qa_report=out / "qa_report.md",
        overlay=out / "overlay.png",
        centerline_dxf=out / "result_centerline.dxf",
        wallsolid_dxf=out / "result_wallsolid.dxf",
    )

