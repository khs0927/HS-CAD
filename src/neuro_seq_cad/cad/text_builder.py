from __future__ import annotations


def add_text(msp, text: str, point: tuple[float, float], height: float = 250.0, layer: str = "TEXT") -> None:
    msp.add_text(text, dxfattribs={"layer": layer, "height": height}).set_placement(point)

