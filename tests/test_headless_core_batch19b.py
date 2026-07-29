from __future__ import annotations

import asyncio

import pytest
from mcp.server.fastmcp import FastMCP

from xicad_mcp.headless_core_batch1 import Approval, Point3D
from xicad_mcp.headless_core_batch19b import (
    BatPlacementMode,
    BreakAndTextRequest,
    BreakOverRequest,
    BreakTextStation,
    BreakToCurrentRequest,
    CandidateKind,
    CircleBreakRequest,
    CircleKeep,
    CurveSample,
    CutCandidate,
    CutterRequest,
    DivideToPolylineRequest,
    EvidenceLevel,
    SourceDisposition,
    TextAngleMode,
    plan_break_and_text,
    plan_break_over,
    plan_break_to_current,
    plan_circle_break,
    plan_cutter,
    plan_divide_to_polyline,
    register_headless_core_batch19b_tools,
)


def point(x: float, y: float = 0) -> Point3D:
    return Point3D(x=x, y=y)


def test_bat_recovers_dcl_inputs_without_deriving_hidden_geometry() -> None:
    request = BreakAndTextRequest(
        document_id="D",
        placement_mode=BatPlacementMode.REPEAT_DISTANCE,
        stations=(
            BreakTextStation(source_handle="A", break_center=point(10), text_point=point(10, 2), rotation_degrees=90),
        ),
        repeat_distance=100,
        first_at_half_spacing=True,
        break_gap=5,
        angle_mode=TextAngleMode.PERPENDICULAR,
        text="도로 중심선",
        text_height=2.5,
        text_layer="TEX",
    )
    plan = plan_break_and_text(request)
    assert plan.breaks[0].gap == 5
    assert plan.texts[0].rotation_degrees == 90
    assert plan.evidence_level is EvidenceLevel.DCL_AND_CONFIG_RECOVERED


def test_bat_repeat_requires_distance() -> None:
    with pytest.raises(ValueError, match="repeat_distance"):
        BreakAndTextRequest(
            document_id="D",
            placement_mode=BatPlacementMode.REPEAT_DISTANCE,
            stations=(
                BreakTextStation(source_handle="A", break_center=point(1), text_point=point(1, 1), rotation_degrees=0),
            ),
            first_at_half_spacing=False,
            break_gap=1,
            angle_mode=TextAngleMode.ZERO,
            text="A",
            text_height=1,
            text_layer="T",
        )


def test_fingerprint_is_stable_and_required_for_execution() -> None:
    dry = BreakToCurrentRequest(
        document_id="D", source_handle="A", first_break_point=point(1), second_break_point=point(2), current_layer="0"
    )
    assert dry.fingerprint() == dry.model_copy().fingerprint()
    with pytest.raises(ValueError, match="exact approval"):
        dry.model_copy(
            update={"dry_run": False, "approval": Approval(approved=True, fingerprint="bad")}
        ).model_validate(
            dry.model_copy(
                update={"dry_run": False, "approval": Approval(approved=True, fingerprint="bad")}
            ).model_dump()
        )
    approved = dry.model_copy(
        update={"dry_run": False, "approval": Approval(approved=True, fingerprint=dry.fingerprint())}
    )
    approved = BreakToCurrentRequest.model_validate(approved.model_dump())
    assert plan_break_to_current(approved).target_layer == "0"


def test_bro_uses_explicit_intersections() -> None:
    plan = plan_break_over(
        BreakOverRequest(
            document_id="D",
            target_handle="T",
            cutter_handles=("C1", "C2"),
            intersection_points=(point(1), point(2)),
            gap=0.5,
        )
    )
    assert [item.center.x for item in plan.breaks] == [1, 2]
    assert plan.evidence_level is EvidenceLevel.SHORTCUT_ONLY_EXPLICIT_POLICY


def test_circle_break_requires_explicit_kept_arc() -> None:
    request = CircleBreakRequest(
        document_id="D",
        source_handle="C",
        center=point(0),
        radius=5,
        start_angle_degrees=10,
        end_angle_degrees=80,
        keep=CircleKeep.COMPLEMENT,
        target_layer="A",
    )
    plan = plan_circle_break(request)
    assert plan.create_arc.start_angle_degrees == 80
    assert plan.create_arc.end_angle_degrees == 370
    assert plan.delete_handles == ("C",)


def test_cut_uses_caller_preclassified_containment_and_protects_xref() -> None:
    request = CutterRequest(
        document_id="D",
        boundary_handle="B",
        candidates=(
            CutCandidate(handle="1", kind=CandidateKind.PRIMITIVE, entirely_inside=True),
            CutCandidate(handle="2", kind=CandidateKind.BLOCK_REFERENCE, entirely_inside=True),
            CutCandidate(handle="3", kind=CandidateKind.HATCH, entirely_inside=False),
            CutCandidate(handle="4", kind=CandidateKind.SOLID, entirely_inside=True, is_xref=True),
        ),
        include_locked=False,
        delete_all_inside=True,
        explode_blocks=True,
        explode_hatches=True,
        convert_solids_to_hatch=True,
        hatch_pattern="ANSI31",
        hatch_scale=10,
        hatch_angle_degrees=0,
    )
    plan = plan_cutter(request)
    assert plan.delete_handles == ("1", "2")
    assert plan.explode_block_handles == ("2",)
    assert not plan.explode_hatch_handles and not plan.solid_to_hatch_handles
    assert plan.containment_preclassified_by_caller


def test_dtp_creates_only_explicit_sample_segments() -> None:
    request = DivideToPolylineRequest(
        document_id="D",
        curves=(
            CurveSample(
                source_handle="S",
                source_entity_type="AcDbSpline",
                sampled_vertices=(point(0), point(1), point(3)),
                layer="A",
            ),
        ),
        max_chord_error=0.01,
        source_disposition=SourceDisposition.REPLACE,
    )
    plan = plan_divide_to_polyline(request)
    assert len(plan.creates) == 2
    assert plan.delete_handles == ("S",)
    assert plan.max_chord_error == 0.01


def test_tools_are_read_only_planners() -> None:
    mcp = FastMCP("batch19b")
    register_headless_core_batch19b_tools(mcp)
    tools = asyncio.run(mcp.list_tools())
    assert {tool.name for tool in tools} == {
        "xicad_plan_bat",
        "xicad_plan_bb",
        "xicad_plan_bro",
        "xicad_plan_cb",
        "xicad_plan_cut",
        "xicad_plan_dtp",
    }
    assert all(tool.annotations and tool.annotations.readOnlyHint for tool in tools)
    assert all(tool.annotations and not tool.annotations.destructiveHint for tool in tools)
