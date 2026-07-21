from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

import win32com.client
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from xicad_mcp.headless_core_batch2 import ExistingStylePolicy, SectionMarkMode, SectionNormalSide
from xicad_mcp.headless_core_batch3 import DoorHinge, DoorSwing, ToiletBoothLegacyVariant
from xicad_mcp.live_batch_remaining import (
    LiveSectionMarkPreviewRequest,
    LiveTableStylePreviewRequest,
    LiveToiletBoothPreviewRequest,
    preview_live_section_mark,
    preview_live_table_style,
    preview_live_toilet_booth,
)

ROOT = Path(__file__).resolve().parents[1]


async def execute(session: ClientSession, tool: str, preview: dict[str, object]) -> None:
    request = {
        key: value
        for key, value in preview.items()
        if key not in {"plan", "mutation", "command_alias", "entity_count"}
    }
    result = await session.call_tool(tool, arguments={"request": request})
    if result.isError:
        raise RuntimeError(f"{tool} failed: {result.content}")


async def smoke() -> None:
    app = win32com.client.GetActiveObject("ZWCAD.Application.2026")
    doc = next(doc for doc in app.Documents if str(doc.Name).casefold() == "drawing1.dwg")
    doc.Activate()
    layer_names = {str(layer.Name).casefold() for layer in doc.Layers}
    for name, color in (("A-TOILET", 3), ("A-ANNO", 1)):
        layer = doc.Layers.Item(name) if name.casefold() in layer_names else doc.Layers.Add(name)
        layer.Color = color
    before = int(doc.ModelSpace.Count)

    env = dict(os.environ)
    env["PYTHONPATH"] = str(ROOT / "src")
    params = StdioServerParameters(command=sys.executable, args=["-m", "xicad_mcp"], cwd=ROOT, env=env)
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            booth = preview_live_toilet_booth(
                LiveToiletBoothPreviewRequest(
                    document_name="Drawing1.dwg",
                    booth={
                        "document_id": "Drawing1.dwg",
                        "legacy_variant": ToiletBoothLegacyVariant.MTB1,
                        "origin": {"x": 7000, "y": 0, "z": 0},
                        "direction_degrees": 0,
                        "stall_count": 2,
                        "stall_width": 1000,
                        "stall_depth": 1500,
                        "door_width": 600,
                        "door_clearance_from_side": 100,
                        "door_hinges": [DoorHinge.LEFT, DoorHinge.RIGHT],
                        "door_swing": DoorSwing.INWARD,
                        "layer": "A-TOILET",
                    },
                )
            )
            await execute(session, "xicad_execute_live_mtb1", booth)
            section = preview_live_section_mark(
                LiveSectionMarkPreviewRequest(
                    document_name="Drawing1.dwg",
                    section={
                        "document_id": "Drawing1.dwg",
                        "mode": SectionMarkMode.SINGLE,
                        "cut_start": {"x": 6800, "y": -500, "z": 0},
                        "cut_end": {"x": 9200, "y": -500, "z": 0},
                        "normal_side": SectionNormalSide.LEFT,
                        "label_start": "A",
                        "label_end": "A",
                        "tail_length": 300,
                        "text_offset": 150,
                        "layer": "A-ANNO",
                        "text_style": "Standard",
                        "text_height": 180,
                    },
                )
            )
            await execute(session, "xicad_execute_live_scc", section)
            table = preview_live_table_style(
                LiveTableStylePreviewRequest(
                    document_name="Drawing1.dwg",
                    desired={
                        "style_name": "HSCAD_MCP_TABLE",
                        "title_text_style": "Standard",
                        "header_text_style": "Standard",
                        "data_text_style": "Standard",
                        "title_text_height": 250,
                        "header_text_height": 200,
                        "data_text_height": 180,
                        "horizontal_cell_margin": 30,
                        "vertical_cell_margin": 20,
                        "flow_direction": "down",
                    },
                    existing_policy=ExistingStylePolicy.UPDATE,
                )
            )
            await execute(session, "xicad_execute_live_table_style", table)

    doc.Regen(1)
    app.ZoomExtents()
    print(json.dumps({"document": doc.Name, "commands": ["MTB1", "SCC", "TBM"], "before_count": before, "after_count": int(doc.ModelSpace.Count), "saved": bool(doc.Saved)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(smoke())
