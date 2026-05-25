from __future__ import annotations

import shutil
from pathlib import Path


class ODAFCAdapter:
    """Adapter boundary for ODA File Converter.

    This class intentionally does not bundle ODAFC or run CAD automation. It
    only reports availability and provides a placeholder conversion contract.
    """

    engine_name = "odafc"

    def is_available(self) -> tuple[bool, str]:
        exe = shutil.which("ODAFileConverter") or shutil.which("ODAFileConverter.exe")
        if exe:
            return True, exe
        return False, "ODA File Converter executable not found on PATH"

    def convert_dwg_to_dxf(self, source_dwg: str | Path, target_dxf: str | Path) -> dict[str, object]:
        available, reason = self.is_available()
        return {
            "source_dwg": str(source_dwg),
            "target_dxf": str(target_dxf),
            "status": "planned" if available else "unavailable",
            "reason": reason,
            "cad_execution": False,
            "sendcommand": False,
        }

