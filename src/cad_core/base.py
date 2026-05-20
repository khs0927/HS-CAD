from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Any

class CADAdapter(ABC):
    @abstractmethod
    def connect(self) -> None: ...

    @abstractmethod
    def open_document(self, path: str) -> Any: ...

    @abstractmethod
    def get_active_document(self) -> Any: ...

    @abstractmethod
    def save_as(self, path: str) -> None: ...

    @abstractmethod
    def scan_modelspace(self) -> list[dict[str, Any]]: ...

    @abstractmethod
    def move_entity(self, handle: str, dx: float, dy: float, dz: float = 0) -> int: ...

    @abstractmethod
    def move_layer(self, layer: str, dx: float, dy: float, dz: float = 0) -> int: ...

    @abstractmethod
    def replace_text(self, find: str, replace: str, layer: str | None = None) -> int: ...

    @abstractmethod
    def list_layers(self) -> list[str]: ...

    @abstractmethod
    def list_blocks(self) -> list[str]: ...

    @abstractmethod
    def close(self) -> None: ...
