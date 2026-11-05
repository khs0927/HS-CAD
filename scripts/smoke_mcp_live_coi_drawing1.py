from __future__ import annotations

import asyncio
import os
import sys
import time
from pathlib import Path

import pythoncom
import win32com.client
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from xicad_mcp.live_zwcad import LiveTextCommand, LiveTextMutationPreviewRequest

ROOT = Path(__file__).resolve().parents[1]


async def exercise() -> None:
    app = win32com.client.GetActiveObject("ZWCAD.Application.2026")
    documents = [doc for doc in app.Documents if doc.Name.casefold() == "drawing1.dwg"]
    if len(documents) != 1:
        raise RuntimeError(f"expected one Drawing1.dwg, found {len(documents)}")
    doc = documents[0]
    doc.Activate()
    before = {str(obj.Handle) for obj in doc.ModelSpace}
    point = win32com.client.VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_R8, [0.0, 2000.0, 0.0])
    doc.StartUndoMark()
    try:
        entity = doc.ModelSpace.AddText("1000", point, 100.0)
    finally:
        doc.EndUndoMark()
    handle = str(entity.Handle)
    preview_request = LiveTextMutationPreviewRequest(
        document_name="Drawing1.dwg",
        command_alias=LiveTextCommand.COI,
        changes=[{"handle": handle, "expected_text": "1000", "replacement_text": "1,000"}],
    )
    environment = dict(os.environ)
    environment["PYTHONPATH"] = str(ROOT / "src")
    parameters = StdioServerParameters(
        command=sys.executable,
        args=["-m", "xicad_mcp"],
        cwd=ROOT,
        env=environment,
    )
    try:
        async with stdio_client(parameters) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                payload = preview_request.model_dump(mode="json")
                preview = await session.call_tool(
                    "xicad_preview_live_text_mutation", arguments={"request": payload}
                )
                if preview.isError:
                    raise RuntimeError(f"MCP preview failed: {preview.content}")
                payload["approval_fingerprint"] = preview_request.fingerprint()
                execution = await session.call_tool(
                    "xicad_execute_live_coi", arguments={"request": payload}
                )
                if execution.isError:
                    raise RuntimeError(f"MCP execution failed: {execution.content}")
        if str(entity.TextString) != "1,000":
            raise RuntimeError("MCP COI postcondition failed")
        print(f"MCP COI changed handle {handle}: 1000 -> {entity.TextString}")
    finally:
        doc.SendCommand("_UNDO\n1\n")
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline and str(entity.TextString) != "1000":
            time.sleep(0.2)
        doc.SendCommand("_UNDO\n1\n")
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            if {str(obj.Handle) for obj in doc.ModelSpace} == before:
                break
            time.sleep(0.2)
        else:
            raise RuntimeError("MCP smoke cleanup did not restore Drawing1")
    print("MCP COI Undo restored Drawing1")


if __name__ == "__main__":
    asyncio.run(exercise())
