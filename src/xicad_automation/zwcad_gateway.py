from __future__ import annotations

import time
from typing import Any, Callable

from src.adapters.zwcad_com_adapter import ZWCADCOMAdapter


class MonitoredZWCADGateway:
    """Adds command-idle monitoring and safe cancellation to the COM adapter."""

    def __init__(self, *, visible: bool = True, version: str | None = None) -> None:
        self.adapter = ZWCADCOMAdapter(visible=visible, version=version, start_if_needed=True)

    def connect(self) -> None:
        self.adapter.connect()

    def open_document(self, path: str) -> Any:
        return self.adapter.open_document(path)

    def get_active_document(self) -> Any:
        return self.adapter.get_active_document()

    def run_command(self, command_text: str) -> None:
        self.adapter.run_command(command_text)

    def scan_modelspace(self) -> list[dict]:
        return self.adapter.scan_modelspace()

    def get_variable(self, name: str, default: Any = None) -> Any:
        try:
            return (self.adapter.doc or self.adapter.get_active_document()).GetVariable(name)
        except Exception:
            return default

    def wait_until_idle(
        self,
        timeout_seconds: float = 120.0,
        poll_seconds: float = 0.2,
        cancel_check: Callable[[], bool] | None = None,
    ) -> bool:
        started = time.monotonic()
        deadline = started + timeout_seconds
        saw_activity = False
        stable_idle_samples = 0
        while time.monotonic() < deadline:
            if cancel_check and cancel_check():
                self.cancel_current_command()
                raise InterruptedError("XiCAD job cancellation requested")
            cmdactive = int(self.get_variable("CMDACTIVE", 0) or 0)
            cmdnames = str(self.get_variable("CMDNAMES", "") or "").strip()
            active = cmdactive != 0 or bool(cmdnames)
            saw_activity = saw_activity or active
            if active:
                stable_idle_samples = 0
            else:
                stable_idle_samples += 1
                elapsed = time.monotonic() - started
                if stable_idle_samples >= 3 and (saw_activity or elapsed >= 0.6):
                    return True
            time.sleep(max(0.05, poll_seconds))
        return False

    def cancel_current_command(self) -> None:
        doc = self.adapter.doc or self.adapter.get_active_document()
        for cancel_text in ("\x03\x03", "\x1b\x1b"):
            try:
                doc.SendCommand(cancel_text)
                return
            except Exception:
                continue

    def save(self) -> None:
        doc = self.adapter.doc or self.adapter.get_active_document()
        doc.Save()

    def close(self) -> None:
        self.adapter.close()
