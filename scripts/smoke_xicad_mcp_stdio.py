"""Headless stdio smoke test for the xiCAD MCP server (no ZWCAD required).

Usage:
    python scripts/smoke_xicad_mcp_stdio.py [path-to-xicad-mcp-executable]

Performs MCP initialize -> tools/list -> CAD-free tool calls and checks that
unsafe input and live tools without an approved request fail closed.
"""

from __future__ import annotations

import asyncio
import shutil
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

ROOT = Path(__file__).resolve().parents[1]


def _text(result) -> str:
    return result.content[0].text if result.content else ""


async def run(command: str) -> int:
    params = StdioServerParameters(command=command, args=[], cwd=str(ROOT))
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            init = await session.initialize()
            tools = (await session.list_tools()).tools
            print(f"server={init.serverInfo.name} protocol={init.protocolVersion} tools={len(tools)}")

            coverage = await session.call_tool("xicad_headless_coverage_summary", {})
            assert not coverage.isError, _text(coverage)
            print("coverage:", " ".join(_text(coverage).split())[:200])

            calc = await session.call_tool(
                "xicad_calculator",
                {"request": {"expression": "(12000-2*200)*(11300-2*200)/1000000", "decimal_places": 3}},
            )
            assert not calc.isError and '"result": "126.440"' in _text(calc), _text(calc)
            print("calculator: 126.440 OK")

            inject = await session.call_tool("xicad_calculator", {"request": {"expression": "__import__('os')"}})
            assert inject.isError, "expression injection must be rejected"
            print("calculator injection rejected OK")

            live = await session.call_tool("xicad_execute_live_ct", {})
            assert live.isError, "live mutation without an approved request must fail closed"
            print("live tool without request rejected OK")
    return 0


def main() -> int:
    command = sys.argv[1] if len(sys.argv) > 1 else (shutil.which("xicad-mcp") or "xicad-mcp")
    return asyncio.run(run(command))


if __name__ == "__main__":
    raise SystemExit(main())
