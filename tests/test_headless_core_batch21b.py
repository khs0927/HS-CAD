from __future__ import annotations

import asyncio

import pytest
from mcp.server.fastmcp import FastMCP

from xicad_mcp.headless_core_batch1 import Approval, Point3D
from xicad_mcp.headless_core_batch21b import (
    AlignItem,
    AlignTargetMode,
    AnchorPosition,
    BothSidesOffsetRequest,
    IntegratedOffsetRequest,
    MeasureRequest,
    MoveAxis,
    ObjectAlignAngleRequest,
    ObjectAlignRequest,
    OffsetEraseRequest,
    OffsetOutput,
    SourceDisposition,
    plan_both_sides_offset,
    plan_integrated_offset,
    plan_measure,
    plan_object_align,
    plan_object_align_angle,
    plan_offset_erase,
    register_headless_core_batch21b_tools,
)


def point(x: float, y: float = 0) -> Point3D:
    return Point3D(x=x, y=y)


def output(handles: tuple[str, ...], y: float) -> OffsetOutput:
    return OffsetOutput(source_handles=handles, vertices=(point(0, y), point(10, y)), layer="A")


def test_mm_keeps_caller_supplied_measure_points() -> None:
    request = MeasureRequest(
        document_id="D", source_handle="L", start_point=point(0), interval=2, placement_points=(point(2), point(4))
    )
    plan = plan_measure(request)
    assert plan.placement_points == (point(2), point(4))
    assert plan.request_fingerprint == request.fingerprint()


def test_oa_recovers_dcl_axis_anchor_copy_and_rotation() -> None:
    request = ObjectAlignRequest(
        document_id="D",
        items=(AlignItem(handle="A", source_anchor=point(1, 2), source_angle_degrees=0),),
        target_mode=AlignTargetMode.SELECTED_OBJECT,
        target_point=point(10, 20),
        target_angle_degrees=90,
        rotate_to_target_angle=True,
        move_axis=MoveAxis.HORIZONTAL,
        anchor_position=AnchorPosition.RIGHT_TOP,
        copy_entities=True,
    )
    plan = plan_object_align(request)
    assert plan.transforms[0].copy_entity
    assert plan.transforms[0].transform[0][0] == pytest.approx(0)
    assert plan.transforms[0].transform[1][3] == 0


def test_oa_rotation_requires_explicit_target_angle() -> None:
    with pytest.raises(ValueError, match="target_angle"):
        ObjectAlignRequest(
            document_id="D",
            items=(AlignItem(handle="A", source_anchor=point(0)),),
            target_mode=AlignTargetMode.POINT,
            target_point=point(1),
            rotate_to_target_angle=True,
            move_axis=MoveAxis.HORIZONTAL,
            anchor_position=AnchorPosition.MIDDLE,
            copy_entities=False,
        )


def test_oaa_requires_distinct_target_and_explicit_angle() -> None:
    request = ObjectAlignAngleRequest(
        document_id="D",
        items=(AlignItem(handle="A", source_anchor=point(0), source_angle_degrees=10),),
        target_point=point(5),
        target_object_handle="T",
        target_angle_degrees=40,
        copy_entities=False,
    )
    plan = plan_object_align_angle(request)
    assert plan.command_alias == "OAA"
    assert plan.transforms[0].transform[0][0] == pytest.approx(0.8660254)


def test_ob_requires_two_explicit_sides() -> None:
    request = BothSidesOffsetRequest(
        document_id="D",
        source_handle="S",
        distance=2,
        positive_side=output(("S",), 2),
        negative_side=output(("S",), -2),
    )
    plan = plan_both_sides_offset(request)
    assert len(plan.creates) == 2 and not plan.delete_handles


def test_oe_deletes_source_only_after_explicit_result() -> None:
    request = OffsetEraseRequest(document_id="D", source_handle="S", distance=2, result=output(("S",), 2))
    assert plan_offset_erase(request).delete_handles == ("S",)


def test_oi_binds_outputs_to_connected_sources() -> None:
    request = IntegratedOffsetRequest(
        document_id="D",
        connected_source_handles=("A", "B"),
        distance=3,
        outputs=(output(("A", "B"), 3),),
        source_disposition=SourceDisposition.REPLACE,
    )
    plan = plan_integrated_offset(request)
    assert plan.delete_handles == ("A", "B")
    with pytest.raises(ValueError, match="outside"):
        IntegratedOffsetRequest(
            document_id="D",
            connected_source_handles=("A", "B"),
            distance=3,
            outputs=(output(("A", "C"), 3),),
            source_disposition=SourceDisposition.PRESERVE,
        )


def test_exact_fingerprint_and_read_only_tools() -> None:
    request = MeasureRequest(
        document_id="D", source_handle="L", start_point=point(0), interval=2, placement_points=(point(2),)
    )
    payload = request.model_copy(
        update={"dry_run": False, "approval": Approval(approved=True, fingerprint="bad")}
    ).model_dump()
    with pytest.raises(ValueError, match="exact approval"):
        MeasureRequest.model_validate(payload)
    mcp = FastMCP("batch21b")
    register_headless_core_batch21b_tools(mcp)
    tools = asyncio.run(mcp.list_tools())
    assert {tool.name for tool in tools} == {
        "xicad_plan_mm",
        "xicad_plan_oa",
        "xicad_plan_oaa",
        "xicad_plan_ob",
        "xicad_plan_oe",
        "xicad_plan_oi",
    }
    assert all(tool.annotations and tool.annotations.readOnlyHint for tool in tools)
    assert all(tool.annotations and not tool.annotations.destructiveHint for tool in tools)
