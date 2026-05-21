"""Image insert workflow (preview only).

This stub provides a preview function that validates the existence of a DXF file
and returns the parameters that would be used for insertion. In a real
environment the function would call ZWCADCOMAdapter to insert the block, but for
unit‑test safety we keep it a no‑op.
"""

from __future__ import annotations

import os
from typing import Dict, Any


def preview_image_insert(dxf_path: str, base_point: list | None = None, scale: float | None = None, rotation: float | None = None) -> Dict[str, Any]:
    """Validate the DXF path and return a preview payload.

    Returns a dictionary with the received arguments and a flag ``valid`` that
    indicates whether the file exists on disk. No drawing mutation is performed.
    """
    valid = bool(dxf_path and os.path.isfile(dxf_path))
    return {
        "valid": valid,
        "dxf_path": dxf_path,
        "base_point": base_point,
        "scale": scale,
        "rotation": rotation,
    }
