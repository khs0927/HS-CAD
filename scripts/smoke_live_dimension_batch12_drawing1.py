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
from xicad_mcp.headless_core_batch12 import LinearOrientation, PolylineVertexPolicy
from xicad_mcp.live_dimension_batch12a import LiveDplPreviewRequest, preview_live_dpl

ROOT = Path(__file__).resolve().parents[1]


def wait_idle(doc: object, timeout: float = 10.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if int(doc.GetVariable("CMDACTIVE")) == 0:
            return
        time.sleep(0.05)
    raise TimeoutError("ZWCAD did not return to an idle command state")


async def execute_dpl(session: ClientSession, preview: dict[str, object]) -> dict[str, object]:
    request = {
        key: value
        for key, value in preview.items()
        if key not in {"plan", "mutation", "command_alias", "create_count"}
    }
    result = await session.call_tool("xicad_execute_live_dpl", arguments={"request": request})
    if result.isError:
        raise RuntimeError(f"DPL MCP execution failed: {result.content}")
    return json.loads(result.content[0].text)


async def smoke() -> None:
    app = win32com.client.GetActiveObject("ZWCAD.Application.2026")
    docs = [doc for doc in app.Documents if str(doc.Name).casefold() == "drawing1.dwg"]
    if len(docs) != 1:
        raise RuntimeError(f"expected one Drawing1.dwg, found {len(docs)}")
    doc = docs[0]
    doc.Activate()
    model = doc.ModelSpace
    polylines = [item for item in model if str(item.ObjectName).casefold() == "acdbpolyline"]
    if not polylines:
        raise RuntimeError("Drawing1.dwg needs at least one lightweight 2D polyline")
    source = polylines[0]
    coordinates = tuple(float(value) for value in source.Coordinates)
    xs = coordinates[0::2]
    ys = coordinates[1::2]
    dimension_point = Point3D(x=(min(xs) + max(xs)) / 2, y=max(ys) + 750, z=0)
    before_count = int(model.Count)

    environment = dict(os.environ)
    environment["PYTHONPATH"] = str(ROOT / "src")
    parameters = StdioServerParameters(command=sys.executable, args=["-m", "xicad_mcp"], cwd=ROOT, env=environment)
    async with stdio_client(parameters) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            def make_preview() -> dict[str, object]:
                return preview_live_dpl(
                    LiveDplPreviewRequest(
                        document_name="Drawing1.dwg",
                        source_handle=str(source.Handle),
                        vertex_policy=PolylineVertexPolicy.CONSECUTIVE_SEGMENTS,
                        orientation=LinearOrientation.ALIGNED,
                        dimension_line_point=dimension_point,
                        style=str(doc.ActiveDimStyle.Name),
                    )
                )

            first = await execute_dpl(session, make_preview())
            first_count = int(model.Count)
            doc.SendCommand("_.UNDO 1 ")
            wait_idle(doc)
            restored_count = int(model.Count)
            if restored_count != before_count:
                raise RuntimeError(
                    f"DPL Undo restoration failed: before={before_count}, after={first_count}, restored={restored_count}"
                )
            final = await execute_dpl(session, make_preview())

    doc.Regen(1)
    app.ZoomExtents()
    print(
        json.dumps(
            {
                "document": str(doc.Name),
                "command": "DPL",
                "source_handle": str(source.Handle),
                "first_created_handles": first["created_handles"],
                "visible_created_handles": final["created_handles"],
                "before_count": before_count,
                "after_first_execute": first_count,
                "after_undo": restored_count,
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
