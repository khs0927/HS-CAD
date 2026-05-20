from __future__ import annotations
from typing import Any
from src.cad_core.base import CADAdapter

class PyRxAdapter(CADAdapter):
    """PyRx/cad-pyrx main adapter skeleton.

    This project intentionally keeps PyRx behind a stable adapter interface because
    PyRx import names and ZWCAD ZRX runtime setup can differ by version.
    Replace the NotImplementedError bodies with actual PyRx calls after confirming
    your local ZWCAD 2025–2027 + cad-pyrx environment.
    """
    def __init__(self):
        self.pyrx: Any = None

    def connect(self) -> None:
        try:
            import pyrx  # type: ignore
            self.pyrx = pyrx
        except Exception as exc:
            raise NotImplementedError(f'PyRx/cad-pyrx is not available or not configured: {exc}') from exc

    def open_document(self, path: str) -> Any:
        raise NotImplementedError('Implement with PyRx document open API for your ZWCAD ZRX runtime.')

    def get_active_document(self) -> Any:
        raise NotImplementedError('Implement with PyRx active database/document API.')

    def save_as(self, path: str) -> None:
        raise NotImplementedError('Implement with PyRx database saveAs API.')

    def scan_modelspace(self) -> list[dict[str, Any]]:
        raise NotImplementedError('Implement by traversing BlockTableRecord.ModelSpace and entities.')

    def move_entity(self, handle: str, dx: float, dy: float, dz: float = 0) -> int:
        raise NotImplementedError('Implement by opening entity ForWrite and applying transform matrix.')

    def move_layer(self, layer: str, dx: float, dy: float, dz: float = 0) -> int:
        raise NotImplementedError('Implement by filtering entities by layer and applying transform matrix.')

    def replace_text(self, find: str, replace: str, layer: str | None = None) -> int:
        raise NotImplementedError('Implement DBText/MText textString mutation.')

    def list_layers(self) -> list[str]:
        raise NotImplementedError('Implement LayerTable iteration.')

    def list_blocks(self) -> list[str]:
        raise NotImplementedError('Implement BlockTable iteration.')

    def close(self) -> None:
        pass
