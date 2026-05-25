"""Base fileizer protocol."""
from __future__ import annotations

from pathlib import Path
from typing import Protocol

from hscad.core.models import FileizedDrawing


class Fileizer(Protocol):
    def fileize(self, input_path: str | Path, out_dir: str | Path | None = None) -> FileizedDrawing: ...
