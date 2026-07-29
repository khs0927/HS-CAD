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

from xicad_mcp.headless_core_batch1 import Point3D
from xicad_mcp.live_batch14a import LiveKPreviewRequest, preview_live_k

ROOT = Path(__file__).resolve().parents[1]


def wait_idle(doc: object, timeout: float = 10.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if int(doc.GetVariable("CMDACTIVE")) == 0:
            return
        time.sleep(0.05)
    raise TimeoutError("ZWCAD did not return to an idle command state")


async def execute_k(session: ClientSession, preview: dict[str, object]) -> dict[str, object]:
    request = {key: value for key, value in preview.items() if key not in {"plan", "mutation", "command_alias"}}
    result = await session.call_tool("xicad_execute_live_k", arguments={"request": request})
    if result.isError:
        raise RuntimeError(f"K MCP execution failed: {result.content}")
    return json.loads(result.content[0].text)


async def smoke() -> None:
    app = win32com.client.GetActiveObject("ZWCAD.Application.2026")
    docs = [doc for doc in app.Documents if str(doc.Name).casefold() == "drawing1.dwg"]
    if len(docs) != 1:
        raise RuntimeError(f"expected one Drawing1.dwg, found {len(docs)}")
    doc = docs[0]
    doc.Activate()
    model = doc.ModelSpace
    source = next(item for item in model if str(item.ObjectName).casefold() == "acdbpolyline")
    coordinates = tuple(float(value) for value in source.Coordinates)
    insertion = Point3D(x=max(coordinates[0::2]) + 1200, y=max(coordinates[1::2]) + 1200, z=0)
    request = LiveKPreviewRequest(
        document_name="Drawing1.dwg",
        insertion_points=(insertion,),
        size=500,
        layer=str(source.Layer),
    )
    before_count = int(model.Count)
    environment = dict(os.environ)
    environment["PYTHONPATH"] = str(ROOT / "src")
    parameters = StdioServerParameters(command=sys.executable, args=["-m", "xicad_mcp"], cwd=ROOT, env=environment)
    async with stdio_client(parameters) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            first = await execute_k(session, preview_live_k(request))
            after_first = int(model.Count)
            doc.SendCommand("_.UNDO 1 ")
            wait_idle(doc)
            after_undo = int(model.Count)
            if after_undo != before_count:
                raise RuntimeError(
                    f"K Undo restoration failed: before={before_count}, after={after_first}, restored={after_undo}"
                )
            final = await execute_k(session, preview_live_k(request))

    doc.Regen(1)
    app.ZoomExtents()
    print(
        json.dumps(
            {
                "document": str(doc.Name),
                "command": "K",
                "first_created_handles": first["created_handles"],
                "visible_created_handles": final["created_handles"],
                "before_count": before_count,
                "after_first_execute": after_first,
                "after_undo": after_undo,
                "final_count": int(model.Count),
                "undo_restoration_verified": True,
                "postcondition_verified": final["postcondition_verified"],
                "saved": bool(doc.Saved),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    asyncio.run(smoke())
