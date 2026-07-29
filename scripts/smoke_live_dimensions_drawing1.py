from __future__ import annotations

import asyncio
import json
import os
import sys
import time
from pathlib import Path

import pythoncom
import win32com.client
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from xicad_mcp.headless_core_batch2 import SourcePolicy
from xicad_mcp.live_dimensions import (
    LiveDividePreviewRequest,
    LiveDtdPreviewRequest,
    LiveJoinPreviewRequest,
    preview_live_dtd,
    preview_live_dvd,
    preview_live_jd,
)

ROOT = Path(__file__).resolve().parents[1]


def vector(x: float, y: float, z: float = 0.0):
    return win32com.client.VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_R8, [x, y, z])


def wait_idle(doc: object, timeout: float = 10.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if int(doc.GetVariable("CMDACTIVE")) == 0:
            return
        time.sleep(0.05)
    raise TimeoutError("ZWCAD did not return to an idle command state")


async def execute(session: ClientSession, tool: str, preview: dict[str, object]) -> None:
    request = {
        key: value
        for key, value in preview.items()
        if key not in {"plan", "mutation", "command_alias"}
    }
    result = await session.call_tool(tool, arguments={"request": request})
    if result.isError:
        raise RuntimeError(f"{tool} failed: {result.content}")


async def smoke() -> None:
    app = win32com.client.GetActiveObject("ZWCAD.Application.2026")
    docs = [doc for doc in app.Documents if str(doc.Name).casefold() == "drawing1.dwg"]
    if len(docs) != 1:
        raise RuntimeError(f"expected one Drawing1.dwg, found {len(docs)}")
    doc = docs[0]
    doc.Activate()
    model = doc.ModelSpace
    before_count = int(model.Count)

    dtd = model.AddDimAligned(vector(0, -1000), vector(2000, -1000), vector(1000, -500))
    dtd.TextOverride = "2000 TYP"
    dvd = model.AddDimAligned(vector(0, -2000), vector(3000, -2000), vector(1500, -1500))
    jd1 = model.AddDimAligned(vector(0, -3000), vector(1500, -3000), vector(750, -2500))
    jd2 = model.AddDimAligned(vector(1500, -3000), vector(3000, -3000), vector(2250, -2500))

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
            dtd_preview = preview_live_dtd(
                LiveDtdPreviewRequest(
                    document_name="Drawing1.dwg",
                    items=(
                        {
                            "dimension_handle": str(dtd.Handle),
                            "expected_current_override": "2000 TYP",
                            "replacement_override": "<>",
                            "detached_text": "TYP",
                            "insertion_point": {"x": 2300, "y": -500, "z": 0},
                            "rotation_degrees": 0,
                        },
                    ),
                )
            )
            await execute(session, "xicad_execute_live_dtd", dtd_preview)

            dvd_preview = preview_live_dvd(
                LiveDividePreviewRequest(
                    document_name="Drawing1.dwg",
                    source_handle=str(dvd.Handle),
                    divisions=3,
                    source_policy=SourcePolicy.PRESERVE,
                )
            )
            await execute(session, "xicad_execute_live_dvd", dvd_preview)

            def jd_preview() -> dict[str, object]:
                return preview_live_jd(
                    LiveJoinPreviewRequest(
                        document_name="Drawing1.dwg",
                        source_handles=(str(jd1.Handle), str(jd2.Handle)),
                        source_policy=SourcePolicy.PRESERVE,
                    )
                )

            count_before_jd = int(model.Count)
            await execute(session, "xicad_execute_live_jd", jd_preview())
            count_after_jd = int(model.Count)
            doc.SendCommand("_.UNDO 1 ")
            wait_idle(doc)
            count_after_undo = int(model.Count)
            undo_verified = count_after_jd == count_before_jd + 1 and count_after_undo == count_before_jd
            if not undo_verified:
                raise RuntimeError(
                    f"JD Undo restoration failed: {count_before_jd}, {count_after_jd}, {count_after_undo}"
                )
            await execute(session, "xicad_execute_live_jd", jd_preview())

    doc.Regen(1)
    app.ZoomExtents()
    print(
        json.dumps(
            {
                "document": str(doc.Name),
                "commands": ["DTD", "DVD", "JD"],
                "fixture_handles": [str(dtd.Handle), str(dvd.Handle), str(jd1.Handle), str(jd2.Handle)],
                "before_count": before_count,
                "after_count": int(model.Count),
                "undo_restoration_verified": undo_verified,
                "saved": bool(doc.Saved),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    asyncio.run(smoke())
