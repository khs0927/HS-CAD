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

    assert len(names) == 894
    assert BATCH_5_TOOLS <= names
    assert BATCH_6_TOOLS <= names
    assert "xicad_headless_coverage_summary" in names
    assert "xicad_execute_live_wal" in names
    assert {
        "xicad_execute_live_ct",
        "xicad_execute_live_dts",
        "xicad_execute_live_flt",
        "xicad_execute_live_sol",
        "xicad_execute_live_tb",
        "xicad_execute_live_tbt",
        "xicad_execute_live_rr",
    } <= names
    assert sum(not tool.annotations.readOnlyHint for tool in tools if tool.annotations) == 199


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
                assert len(listed.tools) == 894
                result = await session.call_tool("xicad_headless_coverage_summary", arguments={})
                assert not result.isError
                preview = await session.call_tool(
                    "xicad_preview_live_wal",
                    arguments={
                        "request": {
                            "document_name": "Drawing1.dwg",
                            "wall": {
                                "thickness": 200.0,
                                "p1": [0.0, 0.0],
                                "p2": [5000.0, 0.0],
                                "p3": [5000.0, 3000.0],
                                "p4": [0.0, 3000.0],
                            },
                        }
                    },
                )
                assert not preview.isError
                for request in (
                    {
                        "operation": "divide_group_sums",
                        "first_group": ["10", "20"],
                        "second_group": ["2", "3"],
                        "decimal_places": 2,
                    },
                    {
                        "operation": "subtract_group_sums",
                        "first_group": ["10", "5"],
                        "second_group": ["3", "2"],
                    },
                    {
                        "operation": "distribution_check",
                        "first_group": ["2", "3"],
                        "second_group": ["4", "5"],
                        "distribution_mode": "group_sum_product",
                    },
                ):
                    calculation = await session.call_tool(
                        "xicad_plan_group_numeric_operation", arguments={"request": request}
                    )
                    assert not calculation.isError

    asyncio.run(exercise_server())
