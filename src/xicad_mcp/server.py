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
from .headless_core_batch7 import register_headless_core_batch7_tools
from .headless_core_batch8 import register_headless_core_batch8_tools
from .headless_core_batch9 import register_headless_core_batch9_tools
from .headless_core_batch10 import register_headless_core_batch10_tools
from .headless_core_batch11 import register_headless_core_batch11_tools
from .headless_coverage import HeadlessCoverageReport, register_headless_coverage_tools
from .live_annotations import register_live_annotation_tools
from .live_batch_remaining import register_live_remaining_tools
from .live_dimensions import register_live_dimension_tools
from .live_layer_batch9a import register_live_layer_batch9a_tools
from .live_layer_batch9b import register_live_layer_batch9b_tools
from .live_layer_batch10a import register_live_layer_batch10a_tools
from .live_layer_batch10b import register_live_layer_batch10b_tools
from .live_layers import register_live_layer_tools
from .live_maintenance import register_live_maintenance_tools
from .live_text_batch7a import register_live_text_batch7a_tools
from .live_text_batch7b import register_live_text_batch7b_tools
from .live_text_batch8a import register_live_text_batch8a_tools
from .live_text_batch8b import register_live_text_batch8b_tools
from .live_zwcad import register_live_zwcad_tools
from .maintenance_cores import register_maintenance_core_tools
from .semantic_reconciliation import FileReconciliationService, register_semantic_reconciliation_tools


def repository_root() -> Path:
    return Path(__file__).resolve().parents[2]


def create_server(root: str | Path | None = None) -> FastMCP:
    """Build the xiCAD MCP server with planning and approved live adapters.

    Live mutations require an exact named drawing, a preview fingerprint, and
    adapter-specific postcondition checks. Unsupported legacy semantics remain
    outside the live registry instead of being reported as successful.
    """
    repo = Path(root).resolve() if root is not None else repository_root()
    mcp = FastMCP("HS-CAD xiCAD Headless")

    register_headless_core_batch1_tools(mcp)
    register_headless_core_batch2_tools(mcp)
    register_headless_core_batch3_tools(mcp)
    register_headless_core_batch4_tools(mcp)
    register_headless_core_batch5_tools(mcp)
    register_headless_core_batch6_tools(mcp)
    register_headless_core_batch7_tools(mcp)
    register_headless_core_batch8_tools(mcp)
    register_headless_core_batch9_tools(mcp)
    register_headless_core_batch10_tools(mcp)
    register_headless_core_batch11_tools(mcp)
    register_maintenance_core_tools(mcp)
    register_live_zwcad_tools(mcp)
    register_live_layer_tools(mcp)
    register_live_layer_batch9a_tools(mcp)
    register_live_layer_batch9b_tools(mcp)
    register_live_layer_batch10a_tools(mcp)
    register_live_layer_batch10b_tools(mcp)
    register_live_dimension_tools(mcp)
    register_live_maintenance_tools(mcp)
    register_live_annotation_tools(mcp)
    register_live_remaining_tools(mcp)
    register_live_text_batch7a_tools(mcp)
    register_live_text_batch7b_tools(mcp)
    register_live_text_batch8a_tools(mcp)
    register_live_text_batch8b_tools(mcp)

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
