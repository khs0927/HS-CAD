from __future__ import annotations

import asyncio
import json
import os
import sys
import time
from pathlib import Path

import win32com.client
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from xicad_mcp.headless_core_batch1 import LayerAffixMode
from xicad_mcp.live_layers import LiveLayerAffixPreviewRequest, preview_live_layer_affix

ROOT = Path(__file__).resolve().parents[1]


async def execute(session: ClientSession, tool: str, preview: dict[str, object]) -> None:
    request = {
        key: value
        for key, value in preview.items()
        if key not in {"command_alias", "mutation"}
    }
    result = await session.call_tool(tool, arguments={"request": request})
    if result.isError:
        raise RuntimeError(f"{tool} failed: {result.content}")


def wait_idle(doc: object, timeout: float = 10.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if int(doc.GetVariable("CMDACTIVE")) == 0:
            return
        time.sleep(0.05)
    raise TimeoutError("ZWCAD did not return to an idle command state")


async def smoke() -> None:
    app = win32com.client.GetActiveObject("ZWCAD.Application.2026")
    matches = [doc for doc in app.Documents if str(doc.Name).casefold() == "drawing1.dwg"]
    if len(matches) != 1:
        raise RuntimeError(f"expected one Drawing1.dwg, found {len(matches)}")
    doc = matches[0]
    doc.Activate()

    names = {str(layer.Name).casefold(): layer for layer in doc.Layers}
    for stale in ("mcp_hscad_demo_live", "mcp_hscad_demo", "hscad_demo"):
        if stale in names:
            names[stale].Name = "HSCAD_DEMO"
            break
    if "hscad_demo" not in {str(layer.Name).casefold() for layer in doc.Layers}:
        doc.Layers.Add("HSCAD_DEMO")
    moved_handles = {"2A7", "2A8", "2A9"}
    for entity in doc.ModelSpace:
        if str(entity.Handle).upper() in moved_handles:
            entity.Layer = "HSCAD_DEMO"

    environment = dict(os.environ)
    environment["PYTHONPATH"] = str(ROOT / "src")
    parameters = StdioServerParameters(
        command=sys.executable,
        args=["-m", "xicad_mcp"],
        cwd=ROOT,
        env=environment,
    )
    async with stdio_client(parameters) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            lpp = preview_live_layer_affix(
                LiveLayerAffixPreviewRequest(
                    document_name="Drawing1.dwg",
                    mode=LayerAffixMode.PREFIX,
                    affix="MCP_",
                    target_names=("HSCAD_DEMO",),
                )
            )
            await execute(session, "xicad_execute_live_lpp", lpp)

            def lps_preview() -> dict[str, object]:
                return preview_live_layer_affix(
                    LiveLayerAffixPreviewRequest(
                        document_name="Drawing1.dwg",
                        mode=LayerAffixMode.SUFFIX,
                        affix="_LIVE",
                        target_names=("MCP_HSCAD_DEMO",),
                    )
                )

            await execute(session, "xicad_execute_live_lps", lps_preview())
            doc.SendCommand("_.UNDO 1 ")
            wait_idle(doc)
            after_undo = {str(layer.Name).casefold() for layer in doc.Layers}
            undo_verified = (
                "mcp_hscad_demo" in after_undo
                and "mcp_hscad_demo_live" not in after_undo
            )
            if not undo_verified:
                raise RuntimeError(f"LPS Undo restoration failed: {sorted(after_undo)}")
            await execute(session, "xicad_execute_live_lps", lps_preview())

    doc.Regen(1)
    app.ZoomExtents()
    final_names = {str(layer.Name) for layer in doc.Layers}
    final_entities = {
        str(entity.Handle): str(entity.Layer)
        for entity in doc.ModelSpace
        if str(entity.Handle).upper() in moved_handles
    }
    print(
        json.dumps(
            {
                "document": str(doc.Name),
                "commands": ["LPP", "LPS"],
                "undo_restoration_verified": undo_verified,
                "final_layer": "MCP_HSCAD_DEMO_LIVE",
                "final_layer_present": "MCP_HSCAD_DEMO_LIVE" in final_names,
                "entity_layers": final_entities,
                "saved": bool(doc.Saved),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    asyncio.run(smoke())
