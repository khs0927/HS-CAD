import asyncio

import pytest
from mcp.server.fastmcp import FastMCP

from xicad_mcp.headless_core_batch1 import Point3D
from xicad_mcp.headless_core_batch19a import (
    HatchDefinition,
    HatchMergeRequest,
    HatchPatternRequest,
    PatternLine,
    PatternWorkMode,
    RandomSelectionMode,
    RandomSolidRequest,
    SolidHatchRequest,
    TableKind,
    TableMethod,
    TableRequest,
    TableTextCell,
    TableTextRequest,
    TableTextSnapshot,
    plan_hatch_merge,
    plan_hatch_pattern,
    plan_random_solid,
    plan_solid_hatch,
    plan_table,
    plan_table_text,
    register_headless_core_batch19a_tools,
)


def hatch(handle: str, pattern: str = "ANSI31") -> HatchDefinition:
    return HatchDefinition(
        handle=handle,
        loops=((Point3D(x=0, y=0), Point3D(x=1, y=0), Point3D(x=1, y=1)),),
        pattern_name=pattern,
        pattern_scale=1,
        pattern_angle_degrees=0,
        color=1,
        layer="H",
        associative=False,
    )


def test_hm_requires_identical_properties() -> None:
    plan = plan_hatch_merge(
        HatchMergeRequest(document_id="D", source_handles=("A", "B"), delete_sources=True), (hatch("A"), hatch("B"))
    )
    assert len(plan.merged_definition.loops) == 2 and plan.delete_handles == ("A", "B")
    with pytest.raises(ValueError, match="identical"):
        plan_hatch_merge(
            HatchMergeRequest(document_id="D", source_handles=("A", "B"), delete_sources=False),
            (hatch("A"), hatch("B", "SOLID")),
        )


def test_hpm_recovers_dcl_but_blocks_pat_write() -> None:
    line = PatternLine(angle_degrees=0, origin_x=0, origin_y=0, delta_x=0, delta_y=10)
    plan = plan_hatch_pattern(
        HatchPatternRequest(
            document_id="D",
            mode=PatternWorkMode.DRAW,
            pattern_name="TEST",
            description="d",
            lines=(line,),
            cell_origin=Point3D(x=0, y=0),
            for_revit_model=True,
        )
    )
    assert plan.header_markers == (";%TYPE=MODEL",) and plan.external_write_blocked
    with pytest.raises(ValueError, match="PAT save"):
        HatchPatternRequest(
            document_id="D",
            mode=PatternWorkMode.SAVE,
            pattern_name="TEST",
            description="d",
            lines=(line,),
            cell_origin=Point3D(x=0, y=0),
            for_revit_model=False,
        )


def test_rds_blocks_unrecovered_random_algorithm() -> None:
    with pytest.raises(ValueError, match="unrecovered"):
        RandomSolidRequest(
            document_id="D",
            candidate_boundary_handles=("A",),
            selection_mode=RandomSelectionMode.LEGACY_RANDOM,
            selected_boundary_handles=("A",),
            layer="H",
            color=1,
            associative=False,
        )
    plan = plan_random_solid(
        RandomSolidRequest(
            document_id="D",
            candidate_boundary_handles=("A", "B"),
            selection_mode=RandomSelectionMode.EXPLICIT,
            selected_boundary_handles=("B",),
            layer="H",
            color=2,
            associative=False,
        )
    )
    assert plan.creates[0].boundary_handle == "B"


def test_sol_creates_confirmed_solid_pattern() -> None:
    plan = plan_solid_hatch(
        SolidHatchRequest(
            document_id="D",
            boundary_handles=("A", "B"),
            layer="H",
            color=256,
            associative=True,
            island_detection="normal",
        )
    )
    assert all(item.pattern_name == "SOLID" for item in plan.creates)


def test_tb_recovers_dcl_counts_and_offsets() -> None:
    plan = plan_table(
        TableRequest(
            document_id="D",
            insertion_point=Point3D(x=0, y=0),
            kind=TableKind.GENERAL,
            method=TableMethod.EXPLICIT_SPACING,
            row_count=2,
            column_count=2,
            row_heights=(5, 10),
            column_widths=(20, 30),
            approximate_division=False,
            layer="T",
        )
    )
    assert plan.x_offsets == (0, 20, 50) and plan.y_offsets == (0, -5, -15)


def test_tbt_bounds_checks_cells() -> None:
    snapshot = TableTextSnapshot(handle="T", row_count=2, column_count=2)
    plan = plan_table_text(
        TableTextRequest(
            document_id="D",
            table_handle="T",
            cells=(TableTextCell(row=1, column=1, text="X"),),
            overwrite_nonempty=False,
        ),
        (snapshot,),
    )
    assert plan.cells[0].text == "X"
    with pytest.raises(ValueError, match="outside"):
        plan_table_text(
            TableTextRequest(
                document_id="D",
                table_handle="T",
                cells=(TableTextCell(row=2, column=0, text="X"),),
                overwrite_nonempty=False,
            ),
            (snapshot,),
        )


def test_live_requires_approval_fingerprint() -> None:
    with pytest.raises(ValueError, match="approval fingerprint"):
        SolidHatchRequest(
            document_id="D",
            boundary_handles=("A",),
            layer="H",
            color=1,
            associative=False,
            island_detection="normal",
            dry_run=False,
        )


def test_registers_six_read_only_tools() -> None:
    mcp = FastMCP("batch19a-test")
    register_headless_core_batch19a_tools(mcp)
    tools = asyncio.run(mcp.list_tools())
    assert len(tools) == 6
    assert all(tool.annotations and tool.annotations.readOnlyHint for tool in tools)
