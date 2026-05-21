from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from .models import FileizedDrawingRecord


class BaseDrawingFileizer(ABC):
    """Base class for all read-only drawing fileizers."""

    @abstractmethod
    def supports(self, path: Path) -> bool:
        raise NotImplementedError

    @abstractmethod
    def is_available(self) -> bool:
        raise NotImplementedError

    @abstractmethod
    def fileize(self, path: Path, out_dir: Path) -> FileizedDrawingRecord:
        raise NotImplementedError

    @abstractmethod
    def get_name(self) -> str:
        raise NotImplementedError

    def get_version(self) -> str:
        return "unknown"
