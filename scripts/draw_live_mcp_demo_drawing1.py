from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

import win32com.client
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from xicad_mcp.live_zwcad import LiveTextCommand, LiveTextMutationPreviewRequest, LiveWalPreviewRequest

ROOT = Path(__file__).resolve().parents[1]


async def call(session: ClientSession, name: str, request: dict[str, object]) -> None:
    result = await session.call_tool(name, arguments={"request": request})
    if result.isError:
        raise RuntimeError(f"{name} failed: {result.content}")


async def draw_demo() -> None:
    app = win32com.client.GetActiveObject("ZWCAD.Application.2026")
    documents = [doc for doc in app.Documents if doc.Name.casefold() == "drawing1.dwg"]
    if len(documents) != 1:
        raise RuntimeError(f"expected one Drawing1.dwg, found {len(documents)}")
    doc = documents[0]
    doc.Activate()
    before = {str(obj.Handle) for obj in doc.ModelSpace}

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
            wall = LiveWalPreviewRequest(
                document_name="Drawing1.dwg",
                wall={
                    "thickness": 200.0,
                    "p1": [0.0, 0.0],
                    "p2": [6000.0, 0.0],
                    "p3": [6000.0, 4000.0],
                    "p4": [0.0, 4000.0],
                },
            )
            wall_payload = wall.model_dump(mode="json")
            wall_payload["approval_fingerprint"] = wall.fingerprint()
            await call(session, "xicad_execute_live_wal", wall_payload)

            labels = (
                (LiveTextCommand.TCT, "HS-CAD xiCAD MCP LIVE DEMO", 0.0, 4600.0, 300.0),
                (LiveTextCommand.M2, "AREA : 24.00 m2", 500.0, 3200.0, 220.0),
                (LiveTextCommand.TIC, "ROOM-010", 500.0, 2600.0, 220.0),
                (LiveTextCommand.TAP, "[WALL]-A", 500.0, 2000.0, 220.0),
            )
            for alias, text, x, y, height in labels:
                preview = LiveTextMutationPreviewRequest(
                    document_name="Drawing1.dwg",
                    command_alias=alias,
                    create_specs=[
                        {
                            "text": text,
                            "insertion_point": {"x": x, "y": y, "z": 0.0},
                            "layer": "0",
                            "text_style": "Standard",
                            "text_height": height,
                            "rotation_degrees": 0.0,
                        }
                    ],
                )
                payload = preview.model_dump(mode="json")
                payload["approval_fingerprint"] = preview.fingerprint()
                await call(session, f"xicad_execute_live_{alias.value.lower()}", payload)

    after_rows = [
        {
            "handle": str(obj.Handle),
            "object_name": str(obj.ObjectName),
            "text": str(obj.TextString) if hasattr(obj, "TextString") else None,
        }
        for obj in doc.ModelSpace
        if str(obj.Handle) not in before
    ]
    app.ZoomExtents()
    print(
        json.dumps(
            {
                "document": doc.Name,
                "before_count": len(before),
                "after_count": len(doc.ModelSpace),
                "created_count": len(after_rows),
                "created": after_rows,
                "undo_performed": False,
                "saved": bool(doc.Saved),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    asyncio.run(draw_demo())
