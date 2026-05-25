"""Namespace shim for local `python -m hscad...` execution."""
from __future__ import annotations

from pathlib import Path

_src_pkg = Path(__file__).resolve().parent.parent / "src" / "hscad"
if _src_pkg.exists():
    __path__.append(str(_src_pkg))  # type: ignore[name-defined]

__all__ = []
