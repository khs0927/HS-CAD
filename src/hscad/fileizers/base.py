"""Base fileizer interface."""
from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from hscad.core.models import FileizedDrawing


class Fileizer(ABC):
    input_types: tuple[str, ...] = ()

    def can_handle(self, path: str | Path) -> bool:
        return Path(path).suffix.lower().lstrip(".") in self.input_types

    @abstractmethod
    def fileize(self, path: str | Path, *, out_dir: str | Path | None = None) -> FileizedDrawing:
        raise NotImplementedError


def detect_input_type(path: str | Path) -> str:
    suffix = Path(path).suffix.lower().lstrip(".")
    return suffix or "unknown"
