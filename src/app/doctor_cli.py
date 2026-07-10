from __future__ import annotations

import importlib.util
import json
import os
import platform
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

import typer
from rich.table import Table

from src.app.cli import app
from src.app.logger import console


@dataclass(frozen=True)
class DoctorCheck:
    name: str
    status: str
    detail: str
    required: bool = True

    @property
    def ok(self) -> bool:
        return self.status in {"ok", "warning"}


def _module_check(import_name: str, *, label: str | None = None, required: bool = True) -> DoctorCheck:
    available = importlib.util.find_spec(import_name) is not None
    return DoctorCheck(
        name=label or import_name,
        status="ok" if available else ("error" if required else "warning"),
        detail="installed" if available else "not installed",
        required=required,
    )


def _candidate_zwcad_paths() -> Iterable[Path]:
    explicit = os.getenv("ZWCAD_EXE")
    if explicit:
        yield Path(explicit)

    roots = [
        os.getenv("ProgramFiles"),
        os.getenv("ProgramFiles(x86)"),
        os.getenv("LOCALAPPDATA"),
    ]
    patterns = (
        "ZWSOFT/ZWCAD 2026/ZWCAD.exe",
        "ZWSOFT/ZWCAD 2025/ZWCAD.exe",
        "ZWSOFT/ZWCAD 2024/ZWCAD.exe",
        "ZWSOFT/ZWCAD/ZWCAD.exe",
    )
    for root in roots:
        if not root:
            continue
        for pattern in patterns:
            yield Path(root) / pattern


def _find_zwcad() -> Path | None:
    for candidate in _candidate_zwcad_paths():
        try:
            if candidate.is_file():
                return candidate.resolve()
        except OSError:
            continue
    return None


def collect_doctor_checks(*, probe_com: bool = False) -> list[DoctorCheck]:
    checks: list[DoctorCheck] = []

    py_ok = (3, 10) <= sys.version_info[:2] < (3, 13)
    checks.append(
        DoctorCheck(
            name="Python",
            status="ok" if py_ok else "error",
            detail=f"{platform.python_version()} (supported: 3.10-3.12)",
        )
    )

    windows = platform.system() == "Windows"
    checks.append(
        DoctorCheck(
            name="Operating system",
            status="ok" if windows else "warning",
            detail=f"{platform.system()} {platform.release()}" + ("; live ZWCAD execution requires Windows" if not windows else ""),
            required=False,
        )
    )

    for import_name, label in (
        ("typer", "Typer CLI"),
        ("pydantic", "Pydantic"),
        ("ezdxf", "DXF engine"),
        ("fitz", "PDF engine"),
        ("cv2", "OpenCV"),
        ("networkx", "NetworkX"),
        ("duckdb", "DuckDB"),
        ("shapely", "Shapely"),
    ):
        checks.append(_module_check(import_name, label=label))

    checks.append(_module_check("win32com", label="pywin32 COM", required=windows))
    checks.append(_module_check("comtypes", label="comtypes COM", required=windows))

    zwcad_path = _find_zwcad() if windows else None
    checks.append(
        DoctorCheck(
            name="ZWCAD installation",
            status="ok" if zwcad_path else ("error" if windows else "warning"),
            detail=str(zwcad_path) if zwcad_path else "not detected; set ZWCAD_EXE when installed in a custom folder",
            required=windows,
        )
    )

    if probe_com:
        if not windows:
            checks.append(DoctorCheck("ZWCAD COM probe", "warning", "skipped outside Windows", required=False))
        else:
            try:
                from src.adapters.zwcad_com_adapter import ZWCADCOMAdapter

                adapter = ZWCADCOMAdapter(visible=True, version=os.getenv("ZWCAD_VERSION"), start_if_needed=False)
                adapter.connect()
                document = adapter.get_active_document()
                name = getattr(document, "Name", "active document")
                checks.append(DoctorCheck("ZWCAD COM probe", "ok", f"connected: {name}"))
            except Exception as exc:  # COM errors vary by ZWCAD build.
                checks.append(DoctorCheck("ZWCAD COM probe", "error", str(exc)))

    return checks


def doctor_payload(*, probe_com: bool = False) -> dict[str, object]:
    checks = collect_doctor_checks(probe_com=probe_com)
    failures = [item for item in checks if item.required and item.status == "error"]
    return {
        "ok": not failures,
        "platform": platform.platform(),
        "python": platform.python_version(),
        "checks": [asdict(item) for item in checks],
        "failure_count": len(failures),
    }


@app.command("doctor")
def doctor(
    probe_com: bool = typer.Option(False, "--probe-com", help="Attach to an already running ZWCAD instance."),
    json_output: Path | None = typer.Option(None, "--json", help="Write the diagnostic result as UTF-8 JSON."),
    strict: bool = typer.Option(False, "--strict", help="Return a non-zero exit code when a required check fails."),
) -> None:
    """Check whether this computer can run HS-CAD and its ZWCAD integration."""
    payload = doctor_payload(probe_com=probe_com)
    table = Table("Check", "Status", "Required", "Detail", title="HS-CAD Environment Doctor")
    for row in payload["checks"]:
        status = str(row["status"])
        rendered_status = {"ok": "[green]OK[/green]", "warning": "[yellow]WARN[/yellow]", "error": "[red]ERROR[/red]"}[status]
        table.add_row(str(row["name"]), rendered_status, "yes" if row["required"] else "no", str(row["detail"]))
    console.print(table)

    if json_output:
        json_output.parent.mkdir(parents=True, exist_ok=True)
        json_output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        console.print(f"[green]Diagnostic JSON written: {json_output}[/green]")

    if strict and not payload["ok"]:
        raise typer.Exit(code=1)
