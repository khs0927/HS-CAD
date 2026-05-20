from __future__ import annotations
from src.adapters.zwcad_com_adapter import ZWCADCOMAdapter

class PyZWCADAdapter(ZWCADCOMAdapter):
    """Optional pyzwcad adapter.

    pyzwcad is not required for MVP. This class currently inherits the robust COM
    fallback and can be extended to use pyzwcad-specific helpers when installed.
    """
    def connect(self) -> None:
        try:
            import pyzwcad  # type: ignore  # noqa: F401
        except Exception:
            pass
        super().connect()
