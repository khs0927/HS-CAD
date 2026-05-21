from __future__ import annotations


def add_linear_dimension_placeholder(msp, p1: tuple[float, float], p2: tuple[float, float], text: str, layer: str = "DIM") -> None:
    # ezdxf dimensions need style setup; preserve a simple editable line/text draft for now.
    msp.add_line(p1, p2, dxfattribs={"layer": layer})
    mid = ((p1[0] + p2[0]) / 2, (p1[1] + p2[1]) / 2)
    msp.add_text(text, dxfattribs={"layer": layer, "height": 180}).set_placement(mid)

