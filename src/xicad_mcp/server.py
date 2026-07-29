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
from .headless_core_batch12 import register_headless_core_batch12_tools
from .headless_core_batch13 import register_headless_core_batch13_tools
from .headless_core_batch14 import register_headless_core_batch14_tools
from .headless_core_batch15 import register_headless_core_batch15_tools
from .headless_core_batch16 import register_headless_core_batch16_tools
from .headless_core_batch17 import register_headless_core_batch17_tools
from .headless_core_batch18 import register_headless_core_batch18_tools
from .headless_core_batch19a import register_headless_core_batch19a_tools
from .headless_core_batch19b import register_headless_core_batch19b_tools
from .headless_core_batch20a import register_headless_core_batch20a_tools
from .headless_core_batch20b import register_headless_core_batch20b_tools
from .headless_core_batch21a import register_headless_core_batch21a_tools
from .headless_core_batch21b import register_headless_core_batch21b_tools
from .headless_core_batch22a import register_headless_core_batch22a_tools
from .headless_core_batch22b import register_headless_core_batch22b_tools
from .headless_core_batch23a import register_headless_core_batch23a_tools
from .headless_core_batch23b import register_headless_core_batch23b_tools
from .headless_core_batch24a import register_headless_core_batch24a_tools
from .headless_core_batch24b import register_headless_core_batch24b_tools
from .headless_core_batch25a import register_headless_core_batch25a_tools
from .headless_core_batch25b import register_headless_core_batch25b_tools
from .headless_core_batch26a import register_headless_core_batch26a_tools
from .headless_core_batch26b import register_headless_core_batch26b_tools
from .headless_core_batch27a import register_headless_core_batch27a_tools
from .headless_core_batch27b import register_headless_core_batch27b_tools
from .headless_core_batch28a import register_headless_core_batch28a_tools
from .headless_core_batch28b import register_headless_core_batch28b_tools
from .headless_core_batch29a import register_headless_core_batch29a_tools
from .headless_core_batch29b import register_headless_core_batch29b_tools
from .headless_core_batch30a import register_headless_core_batch30a_tools
from .headless_core_batch30b import register_headless_core_batch30b_tools
from .headless_core_batch31a import register_headless_core_batch31a_tools
from .headless_core_batch31b import register_headless_core_batch31b_tools
from .headless_core_batch32 import register_headless_core_batch32_tools
from .headless_coverage import HeadlessCoverageReport, register_headless_coverage_tools
from .live_annotations import register_live_annotation_tools
from .live_batch11a import register_live_batch11a_tools
from .live_batch13a import register_live_batch13a_tools
from .live_batch14a import register_live_batch14a_tools
from .live_batch15a import register_live_batch15a_tools
from .live_batch15b import register_live_batch15b_tools
from .live_batch16a import register_live_batch16a_tools
from .live_batch16b import register_live_batch16b_tools
from .live_batch17a import register_live_batch17a_tools
from .live_batch17b import register_live_batch17b_tools
from .live_batch18 import register_live_batch18_tools
from .live_batch19 import register_live_batch19_tools
from .live_batch20 import register_live_batch20_tools
from .live_batch21 import register_live_batch21_tools
from .live_batch22 import register_live_batch22_tools
from .live_batch23 import register_live_batch23_tools
from .live_batch24 import register_live_batch24_tools
from .live_batch25 import register_live_batch25_tools
from .live_batch26 import register_live_batch26_tools
from .live_batch27 import register_live_batch27_tools
from .live_batch28 import register_live_batch28_tools
from .live_batch29 import register_live_batch29_tools
from .live_batch30 import register_live_batch30_tools
from .live_batch31 import register_live_batch31_tools
from .live_batch32 import register_live_batch32_tools
from .live_batch_remaining import register_live_remaining_tools
from .live_dimension_batch11b import register_live_dimension_batch11b_tools
from .live_dimension_batch12a import register_live_dimension_batch12a_tools
from .live_dimension_batch12b import register_live_dimension_batch12b_tools
from .live_dimensions import register_live_dimension_tools
from .live_gap_17_24 import register_live_gap_17_24_tools
from .live_gap_25_32 import register_live_gap_25_32_tools
from .live_geometry_batch13b import register_live_geometry_batch13b_tools
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
    register_headless_core_batch12_tools(mcp)
    register_headless_core_batch13_tools(mcp)
    register_headless_core_batch14_tools(mcp)
    register_headless_core_batch15_tools(mcp)
    register_headless_core_batch16_tools(mcp)
    register_headless_core_batch17_tools(mcp)
    register_headless_core_batch18_tools(mcp)
    register_headless_core_batch19a_tools(mcp)
    register_headless_core_batch19b_tools(mcp)
    register_headless_core_batch20a_tools(mcp)
    register_headless_core_batch20b_tools(mcp)
    register_headless_core_batch21a_tools(mcp)
    register_headless_core_batch21b_tools(mcp)
    register_headless_core_batch22a_tools(mcp)
    register_headless_core_batch22b_tools(mcp)
    register_headless_core_batch23a_tools(mcp)
    register_headless_core_batch23b_tools(mcp)
    register_headless_core_batch24a_tools(mcp)
    register_headless_core_batch24b_tools(mcp)
    register_headless_core_batch25a_tools(mcp)
    register_headless_core_batch25b_tools(mcp)
    register_headless_core_batch26a_tools(mcp)
    register_headless_core_batch26b_tools(mcp)
    register_headless_core_batch27a_tools(mcp)
    register_headless_core_batch27b_tools(mcp)
    register_headless_core_batch28a_tools(mcp)
    register_headless_core_batch28b_tools(mcp)
    register_headless_core_batch29a_tools(mcp)
    register_headless_core_batch29b_tools(mcp)
    register_headless_core_batch30a_tools(mcp)
    register_headless_core_batch30b_tools(mcp)
    register_headless_core_batch31a_tools(mcp)
    register_headless_core_batch31b_tools(mcp)
    register_headless_core_batch32_tools(mcp)
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
    register_live_batch11a_tools(mcp)
    register_live_batch13a_tools(mcp)
    register_live_batch14a_tools(mcp)
    register_live_batch15a_tools(mcp)
    register_live_batch15b_tools(mcp)
    register_live_batch16a_tools(mcp)
    register_live_batch16b_tools(mcp)
    register_live_batch17a_tools(mcp)
    register_live_batch17b_tools(mcp)
    register_live_batch18_tools(mcp)
    register_live_batch19_tools(mcp)
    register_live_batch20_tools(mcp)
    register_live_batch21_tools(mcp)
    register_live_batch22_tools(mcp)
    register_live_batch23_tools(mcp)
    register_live_batch24_tools(mcp)
    register_live_batch25_tools(mcp)
    register_live_batch26_tools(mcp)
    register_live_batch27_tools(mcp)
    register_live_batch28_tools(mcp)
    register_live_batch29_tools(mcp)
    register_live_batch30_tools(mcp)
    register_live_batch31_tools(mcp)
    register_live_batch32_tools(mcp)
    register_live_dimension_batch11b_tools(mcp)
    register_live_dimension_batch12a_tools(mcp)
    register_live_dimension_batch12b_tools(mcp)
    register_live_geometry_batch13b_tools(mcp)
    register_live_gap_17_24_tools(mcp)
    register_live_gap_25_32_tools(mcp)
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
