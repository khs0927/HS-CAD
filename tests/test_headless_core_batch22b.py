from __future__ import annotations

import asyncio

import pytest
from mcp.server.fastmcp import FastMCP

from xicad_mcp.headless_core_batch1 import Approval, Point3D
from xicad_mcp.headless_core_batch22b import (
    AnnotationEntityType,
    BoundingBox,
    BoxMoveRequest,
    DboxAutoCopyRequest,
    DynamicScaleRequest,
    FrameEvidence,
    ProposedLine,
    ProposedScaleAnnotation,
    ScaleAnchor,
    ScaleItem,
    ScaleMultiRequest,
    SequentialScaleItem,
    SequentialScaleRequest,
    SourceDisposition,
    WallRecoverRequest,
    plan_box_move,
    plan_dbox_auto_copy,
    plan_dynamic_scale,
    plan_scale_multi,
    plan_sequential_scale,
    plan_wall_recover,
    register_headless_core_batch22b_tools,
)


def point(x: float, y: float = 0, z: float = 0) -> Point3D:
    return Point3D(x=x, y=y, z=z)


def bounds() -> BoundingBox:
    return BoundingBox(minimum=point(0, 0), maximum=point(10, 20))


def test_sm_uses_recovered_dcl_anchor_to_build_exact_scale_matrix() -> None:
    request = ScaleMultiRequest(
        document_id="D",
        items=(ScaleItem(handle="A", bounds=bounds(), insertion_or_start=point(3, 4)),),
        factor=2,
        anchor=ScaleAnchor.RIGHT_TOP,
    )
    plan = plan_scale_multi(request)
    assert plan.transforms[0].base_point == point(10, 20)
    assert plan.transforms[0].matrix[0] == (2, 0, 0, -10)
    assert plan.request_fingerprint == request.fingerprint()


def test_sm_insert_anchor_uses_explicit_entity_point() -> None:
    request = ScaleMultiRequest(
        document_id="D",
        items=(ScaleItem(handle="A", bounds=bounds(), insertion_or_start=point(3, 4)),),
        factor=0.5,
        anchor=ScaleAnchor.INSERTION_OR_START,
    )
    assert plan_scale_multi(request).transforms[0].base_point == point(3, 4)


def test_ss_applies_one_explicit_remembered_factor_to_ordered_items() -> None:
    request = SequentialScaleRequest(
        document_id="D",
        items=(SequentialScaleItem(handle="A", base_point=point(1)), SequentialScaleItem(handle="B", base_point=point(2))),
        remembered_factor=3,
    )
    plan = plan_sequential_scale(request)
    assert [item.source_handle for item in plan.transforms] == ["A", "B"]
    assert all(item.matrix[0][0] == 3 for item in plan.transforms)


def test_wr_requires_caller_supplied_topology_and_disjoint_deletes() -> None:
    proposal = ProposedLine(source_boundary_handles=("L", "R"), start=point(0), end=point(10), layer="WALL")
    request = WallRecoverRequest(
        document_id="D",
        boundary_line_handles=("L", "R"),
        intermediate_delete_handles=("MID",),
        proposed_lines=(proposal,),
    )
    plan = plan_wall_recover(request)
    assert plan.delete_handles == ("MID",) and plan.creates == (proposal,)
    with pytest.raises(ValueError, match="cannot be intermediate"):
        WallRecoverRequest(
            document_id="D",
            boundary_line_handles=("L", "R"),
            intermediate_delete_handles=("L",),
            proposed_lines=(proposal,),
        )


def test_bmt_explicit_copy_policy_and_reference_points_determine_translation() -> None:
    request = BoxMoveRequest(
        document_id="D",
        source_handles=("A", "B"),
        source_reference=point(10, 20),
        target_reference=point(110, 220),
        disposition=SourceDisposition.COPY,
    )
    plan = plan_box_move(request)
    assert plan.transforms[0].displacement == point(100, 200)
    assert all(item.copy_entity for item in plan.transforms)


def test_das_never_invents_compiled_dynamic_annotation_payload() -> None:
    annotation = ProposedScaleAnnotation(
        entity_type=AnnotationEntityType.TEXT,
        insertion_point=point(5),
        layer="SCALE",
        text="SCALE 1/150",
        text_height=2.5,
    )
    request = DynamicScaleRequest(document_id="D", scale_denominator=150, exact_annotations=(annotation,))
    plan = plan_dynamic_scale(request)
    assert plan.creates == (annotation,)
    with pytest.raises(ValueError, match="requires text"):
        ProposedScaleAnnotation(entity_type=AnnotationEntityType.MTEXT, insertion_point=point(0), layer="SCALE")


def test_dbc_requires_explicit_frame_evidence_and_target_transforms() -> None:
    frame = FrameEvidence(frame_handle="FRAME", frame_bounds=bounds(), source_reference=point(0))
    request = DboxAutoCopyRequest(
        document_id="D",
        frame=frame,
        source_entity_handles=("FRAME", "NOTE"),
        target_reference_points=(point(100), point(200)),
    )
    plan = plan_dbox_auto_copy(request)
    assert len(plan.transforms) == 4
    assert {item.displacement.x for item in plan.transforms} == {100, 200}
    with pytest.raises(ValueError, match="include the recognized frame"):
        DboxAutoCopyRequest(
            document_id="D",
            frame=frame,
            source_entity_handles=("NOTE",),
            target_reference_points=(point(100),),
        )


def test_exact_fingerprint_and_six_read_only_tools() -> None:
    request = SequentialScaleRequest(
        document_id="D",
        items=(SequentialScaleItem(handle="A", base_point=point(0)),),
        remembered_factor=2,
    )
    invalid = request.model_copy(
        update={"dry_run": False, "approval": Approval(approved=True, fingerprint="sha256:wrong")}
    ).model_dump()
    with pytest.raises(ValueError, match="exact approval"):
        SequentialScaleRequest.model_validate(invalid)

    approved = SequentialScaleRequest.model_validate(
        request.model_copy(
            update={"dry_run": False, "approval": Approval(approved=True, fingerprint=request.fingerprint())}
        ).model_dump()
    )
    assert not plan_sequential_scale(approved).dry_run

    mcp = FastMCP("batch22b")
    register_headless_core_batch22b_tools(mcp)
    tools = asyncio.run(mcp.list_tools())
    assert {tool.name for tool in tools} == {
        "xicad_plan_sm",
        "xicad_plan_ss",
        "xicad_plan_wr",
        "xicad_plan_bmt",
        "xicad_plan_das",
        "xicad_plan_dbc",
    }
    assert all(tool.annotations and tool.annotations.readOnlyHint for tool in tools)
    assert all(tool.annotations and not tool.annotations.destructiveHint for tool in tools)
