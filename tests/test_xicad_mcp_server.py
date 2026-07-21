from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from xicad_mcp.server import create_server

ROOT = Path(__file__).resolve().parents[1]

BATCH_5_TOOLS = {
    "xicad_plan_numeric_text_format",
    "xicad_plan_group_numeric_operation",
    "xicad_plan_bulk_number_calculation",
    "xicad_plan_square_metre_to_pyeong",
    "xicad_plan_find_replace",
    "xicad_plan_text_affix",
    "xicad_plan_text_divide",
    "xicad_plan_text_merge",
    "xicad_plan_text_size",
}

BATCH_6_TOOLS = {
    "xicad_plan_m2",
    "xicad_plan_ina",
    "xicad_plan_spn",
    "xicad_plan_lis",
    "xicad_plan_lma",
    "xicad_plan_lna",
    "xicad_plan_qd",
    "xicad_plan_numc",
    "xicad_plan_tic",
    "xicad_plan_tie",
    "xicad_plan_tii",
    "xicad_plan_tin",
}


def test_server_registers_all_planning_tool_families() -> None:
    server = create_server(ROOT)
    tools = asyncio.run(server.list_tools())
    names = {tool.name for tool in tools}

    assert len(names) == 53
    assert BATCH_5_TOOLS <= names
    assert BATCH_6_TOOLS <= names
    assert "xicad_headless_coverage_summary" in names
    assert all(tool.annotations and tool.annotations.readOnlyHint for tool in tools)


def test_stdio_server_lists_and_calls_structured_tool() -> None:
    async def exercise_server() -> None:
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
                listed = await session.list_tools()
                assert len(listed.tools) == 53
                result = await session.call_tool("xicad_headless_coverage_summary", arguments={})
                assert not result.isError

    asyncio.run(exercise_server())
