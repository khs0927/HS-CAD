from __future__ import annotations

from pathlib import Path

from .schema import DxfEntityInfo


def inspect_dxf(source_dxf: str | Path) -> tuple[list[DxfEntityInfo], list[str]]:
    warnings: list[str] = []
    p = Path(source_dxf)
    if not p.exists():
        return [], [f"source DXF missing: {p}"]

    try:
        import ezdxf  # type: ignore
    except Exception:
        return [], ["ezdxf is not installed; inspection skipped"]

    try:
        doc = ezdxf.readfile(str(p))
        msp = doc.modelspace()
        entities: list[DxfEntityInfo] = []
        for e in msp:
            dxf = e.dxf
            entities.append(
                DxfEntityInfo(
                    handle=getattr(dxf, "handle", None),
                    dxftype=e.dxftype(),
                    layer=getattr(dxf, "layer", None),
                    color=getattr(dxf, "color", None),
                    linetype=getattr(dxf, "linetype", None),
                )
            )
        return entities, warnings
    except Exception as exc:
        return [], [f"failed to inspect DXF: {exc}"]
