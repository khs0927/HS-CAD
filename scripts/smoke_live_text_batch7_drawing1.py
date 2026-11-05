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

from xicad_mcp.headless_core_batch7 import TextSwapRequest, TextWidthRequest
from xicad_mcp.live_text_batch7b import preview_live_tsw, preview_live_tw

ROOT = Path(__file__).resolve().parents[1]


def wait_idle(doc: object, timeout: float = 10.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if int(doc.GetVariable("CMDACTIVE")) == 0:
            return
        time.sleep(0.05)
    raise TimeoutError("ZWCAD did not return to an idle command state")


async def call(session: ClientSession, tool: str, request: dict[str, object]) -> None:
    payload = {key: value for key, value in request.items() if key not in {"command_alias", "mutation"}}
    result = await session.call_tool(tool, arguments={"request": payload})
    if result.isError:
        raise RuntimeError(f"{tool} failed: {result.content}")


async def smoke() -> None:
    app = win32com.client.GetActiveObject("ZWCAD.Application.2026")
    doc = next(doc for doc in app.Documents if str(doc.Name).casefold() == "drawing1.dwg")
    doc.Activate()
    objects = {str(entity.Handle).casefold(): entity for entity in doc.ModelSpace}
    handles = ("2AA", "2AB")

    env = dict(os.environ)
    env["PYTHONPATH"] = str(ROOT / "src")
    params = StdioServerParameters(command=sys.executable, args=["-m", "xicad_mcp"], cwd=ROOT, env=env)
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            swap = preview_live_tsw(
                TextSwapRequest(document_id="Drawing1.dwg", first_handle=handles[0], second_handle=handles[1])
            )
            await call(session, "xicad_execute_live_tsw", swap)

            def width_preview() -> dict[str, object]:
                return preview_live_tw(
                    TextWidthRequest(document_id="Drawing1.dwg", target_handles=handles, width_factor=0.85)
                )

            await call(session, "xicad_execute_live_tw", width_preview())
            doc.SendCommand("_.UNDO 1 ")
            wait_idle(doc)
            undo_verified = all(abs(float(objects[handle.casefold()].ScaleFactor) - 1.0) <= 1e-9 for handle in handles)
            if not undo_verified:
                raise RuntimeError("TW Undo restoration failed")
            await call(session, "xicad_execute_live_tw", width_preview())

    doc.Regen(1)
    app.ZoomExtents()
    print(
        json.dumps(
            {
                "document": doc.Name,
                "commands": ["TSW", "TW"],
                "handles": handles,
                "texts": [str(objects[handle.casefold()].TextString) for handle in handles],
                "width_factors": [float(objects[handle.casefold()].ScaleFactor) for handle in handles],
                "undo_restoration_verified": undo_verified,
                "saved": bool(doc.Saved),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    asyncio.run(smoke())
