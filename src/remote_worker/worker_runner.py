from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from src.cad.dxf_inspector import inspect_dxf
from src.cad.ezdxf_modifier import save_modified_dxf
from src.cad.png_exporter import write_png_placeholder
from src.cad.svg_preview import write_svg_preview
from src.remote_worker.drive_client import download_file, upload_file
from src.remote_worker.job_loader import load_job
from src.remote_worker.report_writer import write_change_report
from src.remote_worker.safety_guard import validate_job_safety


def run_job(job_path: str | Path) -> Path:
    job = load_job(job_path)
    validate_job_safety(job)
    out_dir = job.job_output_dir()
    out_dir.mkdir(parents=True, exist_ok=True)

    source_path: Path | None = Path(job.source.file_path) if job.source.file_path else None
    if job.source.type == "google_drive" and job.source.file_id:
        downloaded = download_file(job.source.file_id, out_dir / (job.source.file_name or "source.dxf"))
        if downloaded is not None:
            source_path = downloaded

    modified_dxf = out_dir / "modified.dxf"
    changes = save_modified_dxf(job, source_path, modified_dxf)
    inspection = inspect_dxf(modified_dxf)
    (out_dir / "inspection.json").write_text(json.dumps(inspection, ensure_ascii=False, indent=2), encoding="utf-8")

    if "svg" in job.outputs:
        write_svg_preview(modified_dxf, out_dir / "preview.svg")
    if "png" in job.outputs:
        write_png_placeholder(out_dir / "preview.png", f"HS-CAD Remote DXF Worker: {job.job_id}")
    if "change_report" in job.outputs:
        write_change_report(job, out_dir, changes, inspection)

    drive_output_folder = os.environ.get("GDRIVE_OUTPUT_FOLDER_ID")
    if drive_output_folder:
        for file in out_dir.iterdir():
            if file.is_file():
                upload_file(file, drive_output_folder)

    return out_dir


def main() -> None:
    parser = argparse.ArgumentParser(description="Run HS-CAD remote DXF worker job")
    parser.add_argument("--job", required=True, help="Path to job JSON")
    args = parser.parse_args()
    out_dir = run_job(args.job)
    print(f"HS-CAD remote worker output: {out_dir}")


if __name__ == "__main__":
    main()
