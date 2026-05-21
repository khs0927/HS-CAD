from __future__ import annotations


def add_solid_hatch(msp, polygon: list[tuple[float, float]], layer: str = "WAL_HATCH") -> tuple[bool, str | None]:
    if len(polygon) < 3:
        return False, "hatch_skipped: polygon has fewer than 3 points"
    if polygon[0] != polygon[-1]:
        polygon = polygon + [polygon[0]]
    hatch = msp.add_hatch(color=8, dxfattribs={"layer": layer})
    hatch.paths.add_polyline_path(polygon, is_closed=True)
    return True, None

