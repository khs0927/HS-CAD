from __future__ import annotations
from pathlib import Path
from typing import Any

class EzDxfAdapter:
    def read_dxf_entities(self, path: str | Path) -> list[dict[str, Any]]:
        import ezdxf
        doc = ezdxf.readfile(str(path))
        msp = doc.modelspace()
        out: list[dict[str, Any]] = []
        for e in msp:
            out.append({'dxftype': e.dxftype(), 'layer': e.dxf.layer, 'handle': e.dxf.handle})
        return out
