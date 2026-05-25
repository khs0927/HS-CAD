from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any


DEFAULT_FULL_SEQUENCE = [
    "analysis_core_megapack",
    "analysis_graph_megapack",
    "analysis_advanced_megapack",
    "analysis_ops_megapack",
    "analysis_automation_megapack",
    "analysis_evidence_megapack",
    "analysis_export_megapack",
    "analysis_storage_megapack",
    "analysis_report_megapack",
]


REPORT_SEQUENCE = [
    "analysis_evidence_megapack",
    "analysis_export_megapack",
    "analysis_storage_megapack",
    "analysis_report_megapack",
]


def run_pipeline_sequence(
    workspace: str | Path,
    *,
    sequence: list[str] | None = None,
    dry_run: bool = True,
    stop_on_error: bool = True,
    timeout_sec: int = 1800,
    repo_root: str | Path = ".",
) -> dict[str, Any]:
    """Run or dry-run HS-CAD worker sequence.

    This is intentionally independent from the existing worker CLI internals.
    It shells out to `python -X utf8 -m src.main hscad-worker-run ...`.

    Default dry_run=True for safety.
    """
    ws = str(workspace)
    root = Path(repo_root)
    sequence = sequence or DEFAULT_FULL_SEQUENCE
    output_dir = Path(ws) / "pipeline_execution"
    output_dir.mkdir(parents=True, exist_ok=True)

    results: list[dict[str, Any]] = []
    for index, worker in enumerate(sequence, start=1):
        command = [sys.executable, "-X", "utf8", "-m", "src.main", "hscad-worker-run", worker, "--workspace", ws]
        started = time.time()
        stdout_path = output_dir / f"{index:02d}_{worker}.stdout.log"
        stderr_path = output_dir / f"{index:02d}_{worker}.stderr.log"

        row: dict[str, Any] = {
            "order": index,
            "worker": worker,
            "command": command,
            "dry_run": dry_run,
            "status": "dry_run" if dry_run else "planned",
            "returncode": None,
            "duration_sec": 0.0,
            "stdout_log": str(stdout_path),
            "stderr_log": str(stderr_path),
        }

        if dry_run:
            stdout_path.write_text("DRY RUN: " + " ".join(command) + "\n", encoding="utf-8")
            stderr_path.write_text("", encoding="utf-8")
        else:
            try:
                completed = subprocess.run(
                    command,
                    cwd=str(root),
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    capture_output=True,
                    timeout=timeout_sec,
                )
                stdout_path.write_text(completed.stdout or "", encoding="utf-8")
                stderr_path.write_text(completed.stderr or "", encoding="utf-8")
                row["returncode"] = completed.returncode
                row["status"] = "ok" if completed.returncode == 0 else "error"
            except subprocess.TimeoutExpired as exc:
                row["status"] = "timeout"
                row["error"] = str(exc)
                stderr_path.write_text(str(exc), encoding="utf-8")
            except Exception as exc:
                row["status"] = "error"
                row["error"] = str(exc)
                stderr_path.write_text(str(exc), encoding="utf-8")

        row["duration_sec"] = round(time.time() - started, 6)
        results.append(row)

        if row["status"] in {"error", "timeout"} and stop_on_error:
            break

    payload = {
        "backend": "pipeline_execution_reporter",
        "schema_version": "0.1",
        "parameters": {
            "workspace": ws,
            "dry_run": dry_run,
            "stop_on_error": stop_on_error,
            "timeout_sec": timeout_sec,
            "repo_root": str(root),
        },
        "summary": {
            "planned_count": len(sequence),
            "result_count": len(results),
            "ok_count": sum(1 for row in results if row["status"] == "ok"),
            "dry_run_count": sum(1 for row in results if row["status"] == "dry_run"),
            "error_count": sum(1 for row in results if row["status"] in {"error", "timeout"}),
        },
        "results": results,
        "todo": [
            "Validate hscad-worker-run option compatibility locally.",
            "Add resume-from-worker after real execution validation.",
            "Add artifact diffing after each worker.",
            "Add CI exit mode after rule thresholds are stable.",
        ],
        "warnings": ["dry_run=True by default; no workers are executed unless explicitly disabled."] if dry_run else [],
    }

    report_json = output_dir / "PIPELINE_EXECUTION_REPORT.json"
    report_md = output_dir / "PIPELINE_EXECUTION_REPORT.md"
    report_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    report_md.write_text(_markdown(payload), encoding="utf-8")
    return payload


def _markdown(payload: dict[str, Any]) -> str:
    s = payload.get("summary") or {}
    lines = [
        "# Pipeline Execution Report",
        "",
        f"- Planned: `{s.get('planned_count')}`",
        f"- Results: `{s.get('result_count')}`",
        f"- OK: `{s.get('ok_count')}`",
        f"- Dry-run: `{s.get('dry_run_count')}`",
        f"- Errors: `{s.get('error_count')}`",
        "",
        "| Order | Worker | Status | Return code | Duration |",
        "|---:|---|---|---:|---:|",
    ]
    for row in payload.get("results") or []:
        lines.append(f"| {row.get('order')} | {row.get('worker')} | {row.get('status')} | {row.get('returncode')} | {row.get('duration_sec')} |")
    lines.append("")
    return "\n".join(lines)
