"""LISP live loader utilities for ZWCAD.

The functions provide a preview of the ``(load "path")`` command and an
optional execution path that actually sends the command to the active ZWCAD
session. All path handling uses ``Path.as_posix()`` which was introduced in
the earlier bug‑fix.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

from src.adapters.zwcad_com_adapter import ZWCADCOMAdapter


def build_lisp_load_command(path: Path) -> str:
    """Return the exact ``(load "...")`` command string for *path*.

    The function normalises the path to POSIX style (forward slashes) because
    AutoLISP expects that format irrespective of the underlying Windows file
    system.
    """
    posix_path = path.as_posix()
    return f"(load \"{posix_path}\")"


def validate_lisp_path(path: Path) -> Dict[str, Any]:
    """Validate *path* and return a small dictionary describing the result.

    The dictionary contains:
    - ``exists`` – whether the file exists on disk
    - ``original`` – the original string representation
    - ``posix`` – the forward‑slash representation used by LISP
    """
    return {
        "exists": path.is_file(),
        "original": str(path),
        "posix": path.as_posix(),
    }


def preview_lisp_load(path: Path) -> Dict[str, Any]:
    """Produce a preview payload for loading a LISP file.

    No command is sent to ZWCAD – the function merely validates the path and
    constructs the load command string.
    """
    validation = validate_lisp_path(path)
    command = build_lisp_load_command(path)
    return {"validation": validation, "command": command, "executed": False}


def send_lisp_load_if_allowed(path: Path, allow_execute: bool = False) -> Dict[str, Any]:
    """Validate *path* and optionally send the load command to ZWCAD.

    If ``allow_execute`` is ``False`` the function behaves like
    :func:`preview_lisp_load`. When ``True`` and the file exists, a
    ``ZWCADCOMAdapter`` instance is created, connected and ``load_lisp`` is
    called.
    """
    result = preview_lisp_load(path)
    if allow_execute and result["validation"]["exists"]:
        adapter = ZWCADCOMAdapter(visible=True, start_if_needed=False)
        adapter.connect()
        # The adapter's ``load_lisp`` method already applies Path.as_posix().
        adapter.load_lisp(str(path))
        result["executed"] = True
    return result
