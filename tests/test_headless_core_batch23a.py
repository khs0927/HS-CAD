import asyncio

import pytest
from mcp.server.fastmcp import FastMCP

from xicad_mcp.headless_core_batch1 import Approval, Point3D
from xicad_mcp.headless_core_batch23a import (
    Box2D,
    ChangeBlockDimensionScaleRequest,
    CheckPlotBoxRequest,
    DrawingListRecord,
    DrawingUnit,
    FindFrameScaleRequest,
    FrameExtent,
    FramePlacement,
    FrameSortRequest,
    MakeDrawingListRequest,
    NestedDimensionSnapshot,
    NumberingTarget,
    PaperSize,
    PlotBoundarySnapshot,
    TitleNumberingRequest,
    plan_change_block_dimension_scale,
    plan_check_plot_box,
    plan_find_frame_scale,
    plan_frame_sort,
    plan_make_drawing_list,
    plan_title_numbering,
    register_headless_core_batch23a_tools,
)


def test_dbs_uses_only_explicit_frame_anchors() -> None:
    request = FrameSortRequest(
        document_id="D",
        placements=(
            FramePlacement(
                block_reference_handle="A",
                source_anchor=Point3D(x=10, y=20, z=1),
                target_anchor=Point3D(x=110, y=5, z=1),
            ),
        ),
    )
    plan = plan_frame_sort(request)
    assert plan.moves[0].displacement == Point3D(x=100, y=-15, z=0)
    assert plan.request_fingerprint == request.fingerprint()


def test_dfs_computes_a3_scale_and_explicit_variable_proposals() -> None:
    plan = plan_find_frame_scale(
        FindFrameScaleRequest(
            document_id="D",
            frames=(FrameExtent(block_reference_handle="A", width=42000, height=29700),),
            paper_size=PaperSize.A3,
            drawing_unit=DrawingUnit.MILLIMETER,
            allow_rotated_sheet=False,
            proposed_ltscale=100,
            proposed_dimscale=100,
        )
    )
    assert plan.findings[0].scale_denominator == pytest.approx(100)
    assert plan.findings[0].within_tolerance
    assert [(item.name, item.value) for item in plan.system_variable_proposals] == [
        ("LTSCALE", 100),
        ("DIMSCALE", 100),
    ]


def test_dsb_omits_unchanged_dimensions() -> None:
    plan = plan_change_block_dimension_scale(
        ChangeBlockDimensionScaleRequest(
            document_id="D",
            dimensions=(
                NestedDimensionSnapshot(
                    block_reference_handle="B", dimension_handle="D1", current_dimscale=50
                ),
                NestedDimensionSnapshot(
                    block_reference_handle="B", dimension_handle="D2", current_dimscale=100
                ),
            ),
            target_dimscale=100,
        )
    )
    assert [item.dimension_handle for item in plan.updates] == ["D1"]
    with pytest.raises(ValueError, match="at least one"):
        ChangeBlockDimensionScaleRequest(
            document_id="D",
            dimensions=(
                NestedDimensionSnapshot(
                    block_reference_handle="B", dimension_handle="D1", current_dimscale=100
                ),
            ),
            target_dimscale=100,
        )


def test_mdl_preserves_caller_order_and_dcl_columns() -> None:
    plan = plan_make_drawing_list(
        MakeDrawingListRequest(
            document_id="D",
            ordered_records=(
                DrawingListRecord(
                    frame_handle="F2",
                    drawing_number="002",
                    drawing_name="PLAN",
                    a1_scale="1:100",
                    a3_scale="1:200",
                    revision="A",
                ),
                DrawingListRecord(
                    frame_handle="F1",
                    drawing_number="001",
                    drawing_name="SECTION",
                    a1_scale="1:50",
                    a3_scale="1:100",
                ),
            ),
            list_scale=100,
            text_height=2.5,
            line_gap=5,
            column_gaps=(18, 58, 10, 10),
            title_prefix="ARCH-",
            text_layer="TEXT",
            line_layer="TABLE",
        )
    )
    assert [row.values[0] for row in plan.rows] == ["002", "001"]
    assert plan.rows[0].values == ("002", "ARCH-PLAN", "1:100", "1:200", "A")


def test_pbs_reports_matched_mismatched_and_missing_snapshot() -> None:
    expected = Box2D(minimum_x=0, minimum_y=0, maximum_x=420, maximum_y=297)
    plan = plan_check_plot_box(
        CheckPlotBoxRequest(
            document_id="D",
            coordinate_tolerance=0.01,
            frames=(
                PlotBoundarySnapshot(
                    block_reference_handle="A", expected_boundary=expected, observed_boundary=expected
                ),
                PlotBoundarySnapshot(
                    block_reference_handle="B",
                    expected_boundary=expected,
                    observed_boundary=Box2D(minimum_x=0, minimum_y=0, maximum_x=421, maximum_y=297),
                ),
                PlotBoundarySnapshot(block_reference_handle="C", expected_boundary=expected),
            ),
        )
    )
    assert [item.status for item in plan.findings] == ["matched", "mismatched", "missing_observed_boundary"]


def test_tn_renders_signed_padded_explicit_sequence() -> None:
    plan = plan_title_numbering(
        TitleNumberingRequest(
            document_id="D",
            ordered_targets=(
                NumberingTarget(
                    block_reference_handle="B1", attribute_handle="A1", attribute_tag="SHEET", old_text="x"
                ),
                NumberingTarget(
                    block_reference_handle="B2", attribute_handle="A2", attribute_tag="SHEET", old_text="y"
                ),
            ),
            prefix="A-",
            starting_number=9,
            step=2,
            suffix="-R",
            zero_pad_width=3,
        )
    )
    assert [item.new_text for item in plan.updates] == ["A-009-R", "A-011-R"]


def test_non_dry_run_requires_exact_canonical_fingerprint() -> None:
    draft = FrameSortRequest(
        document_id="D",
        placements=(
            FramePlacement(
                block_reference_handle="A",
                source_anchor=Point3D(x=0, y=0),
                target_anchor=Point3D(x=1, y=0),
            ),
        ),
    )
    with pytest.raises(ValueError, match="exact approval fingerprint"):
        FrameSortRequest(
            document_id="D",
            placements=draft.placements,
            dry_run=False,
            approval=Approval(approved=True, fingerprint="sha256:wrong"),
        )
    approved = FrameSortRequest(
        document_id="D",
        placements=draft.placements,
        dry_run=False,
        approval=Approval(approved=True, fingerprint=draft.fingerprint()),
    )
    assert not approved.dry_run


def test_registers_six_read_only_tools() -> None:
    mcp = FastMCP("batch23a-test")
    register_headless_core_batch23a_tools(mcp)
    tools = asyncio.run(mcp.list_tools())
    assert len(tools) == 6
    assert all(tool.annotations and tool.annotations.readOnlyHint for tool in tools)
    assert all(tool.annotations and not tool.annotations.destructiveHint for tool in tools)
