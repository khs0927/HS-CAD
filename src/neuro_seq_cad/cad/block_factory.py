from __future__ import annotations


def ensure_blocks(doc) -> None:
    if "DOOR_BLOCK" not in doc.blocks:
        block = doc.blocks.new(name="DOOR_BLOCK")
        block.add_line((0, 0), (900, 0), dxfattribs={"layer": "DOOR"})
        block.add_arc((0, 0), 900, 0, 90, dxfattribs={"layer": "DOOR_SWING"})
    if "WINDOW_BLOCK" not in doc.blocks:
        block = doc.blocks.new(name="WINDOW_BLOCK")
        block.add_line((0, -40), (1000, -40), dxfattribs={"layer": "WINBAR"})
        block.add_line((0, 40), (1000, 40), dxfattribs={"layer": "WINBAR"})
        block.add_line((0, 0), (1000, 0), dxfattribs={"layer": "WIN"})

