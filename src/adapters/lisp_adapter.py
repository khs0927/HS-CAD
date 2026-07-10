from __future__ import annotations

from pathlib import Path
from typing import Any


class LispAdapter:
    def __init__(self, com_adapter: Any):
        self.com_adapter = com_adapter

    @staticmethod
    def _normalize_lisp_path(path: str | Path) -> str:
        """Return an AutoLISP-safe path independent of the host OS."""
        normalized = str(path).replace("\\", "/")
        return normalized.replace('"', '\\"')

    def load_lisp(self, path: str | Path) -> None:
        doc = self.com_adapter.get_active_document()
        normalized = self._normalize_lisp_path(path)
        doc.SendCommand(f'(load "{normalized}")\n')

    def send_command(self, command: str) -> None:
        doc = self.com_adapter.get_active_document()
        doc.SendCommand(command if command.endswith("\n") else command + "\n")
