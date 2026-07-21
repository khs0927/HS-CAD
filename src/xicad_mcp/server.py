from __future__ import annotations

from pathlib import Path

from mcp.server.fastmcp import FastMCP

from .binary_recovery import FileBinaryRecoveryService, register_binary_recovery_tools
from .compatibility_aliases import FileCompatibilityService, register_compatibility_alias_tools
from .headless_core_batch1 import register_headless_core_batch1_tools
from .headless_core_batch2 import register_headless_core_batch2_tools
from .headless_core_batch3 import register_headless_core_batch3_tools
from .headless_core_batch4 import register_headless_core_batch4_tools
from .headless_core_batch5 import register_headless_core_batch5_tools
from .headless_core_batch6 import register_headless_core_batch6_tools
from .headless_coverage import HeadlessCoverageReport, register_headless_coverage_tools
from .maintenance_cores import register_maintenance_core_tools
from .semantic_reconciliation import FileReconciliationService, register_semantic_reconciliation_tools


def repository_root() -> Path:
    return Path(__file__).resolve().parents[2]


def create_server(root: str | Path | None = None) -> FastMCP:
    """Build the local, planning-only xiCAD MCP server.

    No registered tool connects to CAD or mutates a drawing. Live adapter tools
    stay excluded until their postconditions and Undo restoration are validated.
    """
    repo = Path(root).resolve() if root is not None else repository_root()
    mcp = FastMCP("HS-CAD xiCAD Headless")

    register_headless_core_batch1_tools(mcp)
    register_headless_core_batch2_tools(mcp)
    register_headless_core_batch3_tools(mcp)
    register_headless_core_batch4_tools(mcp)
    register_headless_core_batch5_tools(mcp)
    register_headless_core_batch6_tools(mcp)
    register_maintenance_core_tools(mcp)

    register_compatibility_alias_tools(
        mcp,
        FileCompatibilityService(repo / "catalog/compatibility/legacy-alias-wrappers.json"),
    )
    register_binary_recovery_tools(
        mcp,
        FileBinaryRecoveryService(repo / "catalog/recovery/binary-recovery.json"),
    )
    register_semantic_reconciliation_tools(
        mcp,
        FileReconciliationService(repo / "catalog/compatibility/semantic-reconciliation.json"),
    )

    coverage = HeadlessCoverageReport.model_validate_json(
        (repo / "catalog/headless/headless-coverage-357.json").read_text(encoding="utf-8")
    )
    register_headless_coverage_tools(mcp, coverage)
    return mcp


def main() -> None:
    create_server().run(transport="stdio")


if __name__ == "__main__":
    main()
