"""ODA File Converter boundary.

This adapter is a boundary only: it performs configured conversion if the user
has provided an executable path. It never falls back to COM full scan.
"""
from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class OdaFcResult:
    ok: bool
    input_path: str
    output_path: str | None = None
    message: str = ""
    command: list[str] | None = None


class OdaFileConverterAdapter:
    def __init__(self, executable: str | None = None) -> None:
        self.executable = executable or os.environ.get("HSCAD_ODAFC_EXE")

    def is_configured(self) -> bool:
        return bool(self.executable and Path(self.executable).exists())

    def convert_dwg_to_dxf(self, input_path: str | Path, out_dir: str | Path) -> OdaFcResult:
        src = Path(input_path)
        out = Path(out_dir)
        out.mkdir(parents=True, exist_ok=True)
        expected = out / f"{src.stem}.dxf"
        if not self.is_configured():
            return OdaFcResult(False, str(src), str(expected), "ODA File Converter executable is not configured")
        command = [str(self.executable), str(src.parent), str(out), "ACAD2018", "DXF", "0", "1", str(src.name)]
        try:
            completed = subprocess.run(command, check=False, capture_output=True, text=True, timeout=120)
            if expected.exists():
                return OdaFcResult(True, str(src), str(expected), "converted", command)
            return OdaFcResult(False, str(src), str(expected), completed.stderr or completed.stdout or "conversion output not found", command)
        except Exception as exc:
            return OdaFcResult(False, str(src), str(expected), f"ODAFC execution failed: {exc}", command)
