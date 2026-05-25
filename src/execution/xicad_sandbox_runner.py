from __future__ import annotations

import shutil
import time
from pathlib import Path
from typing import Any

from src.analysis.dxf_delta_extractor import DXFDeltaReport, extract_dxf_delta
from src.app.logger import warn
from src.execution.scan_snapshot import build_scan_snapshot


class XiCADSandboxRunner:
    """
    Executes a XiCAD command in a safe, isolated ZWCAD document (sandbox),
    and extracts the geometric/layer delta (signature) produced by the command.
    """

    def __init__(self, adapter: Any):
        self.adapter = adapter

    def extract_signature(
        self,
        sandbox_dwg_template: str,
        working_dwg_path: str,
        command_hint: str,
        input_sequence: str,
        delay_seconds: float = 1.0,
    ) -> DXFDeltaReport:
        template_path = Path(sandbox_dwg_template)
        working_path = Path(working_dwg_path)

        if not template_path.exists():
            raise FileNotFoundError(f"Sandbox template not found: {template_path}")

        # 1. Copy template to isolated working path
        working_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(str(template_path), str(working_path))

        # 2. Open sandbox document
        try:
            doc = self.adapter.open_document(str(working_path.resolve()))
        except Exception as e:
            raise RuntimeError(f"Failed to open working document: {e}")

        # Ensure document is activated (focus) for SendCommand
        try:
            self.adapter.app.ActiveDocument = doc
        except Exception as e:
            warn(f"Could not explicitly set active document: {e}")

        # 3. Snapshot BEFORE
        before = build_scan_snapshot(self.adapter, str(working_path.resolve()))

        # 4. Execute Command via SendCommand
        # Replace string literal '\n' with actual newline carriage return
        formatted_sequence = input_sequence.replace("\\n", "\n")
        doc.SendCommand(formatted_sequence)

        # 5. Wait for LISP/FAS execution to finish
        time.sleep(delay_seconds)
        doc.Save()

        # 6. Snapshot AFTER
        after = build_scan_snapshot(self.adapter, str(working_path.resolve()))

        # 7. Extract Delta
        delta = extract_dxf_delta(before, after, command_hint=command_hint)
        return delta
