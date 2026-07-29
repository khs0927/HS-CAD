import asyncio

import pytest
from mcp.server.fastmcp import FastMCP

from xicad_mcp.headless_core_batch1 import Approval, Point3D
from xicad_mcp.headless_core_batch22a import (
    BoundingBox3D,
    DrawOrderMode,
    OffsetBasis,
    OffsetCurrentLayerRequest,
    OffsetMultiRequest,
    RandomCopyRequest,
    RotateMultiRequest,
    RotationTarget,
    SolidMoveBackRequest,
    ToleranceOffsetRequest,
    plan_offset_current_layer,
    plan_offset_multi,
    plan_offset_tolerance,
    plan_random_copy,
    plan_rotate_multi,
    plan_solid_move_back,
    register_headless_core_batch22a_tools,
)


def test_om_distinguishes_original_and_chained_offsets() -> None:
    request = OffsetMultiRequest(
        document_id="D", source_handle="A", signed_distances=(10, -20), basis=OffsetBasis.PREVIOUS_RESULT
    )
    plan = plan_offset_multi(request)
    assert [item.source_handle for item in plan.operations] == ["A", "OM:1"]
    assert plan.request_fingerprint == request.fingerprint()
    original = plan_offset_multi(
        OffsetMultiRequest(document_id="D", source_handle="A", signed_distances=(10, 20), basis=OffsetBasis.ORIGINAL)
    )
    assert [item.source_handle for item in original.operations] == ["A", "A"]


def test_oo_captures_current_layer_and_rejects_zero_distance() -> None:
    plan = plan_offset_current_layer(
        OffsetCurrentLayerRequest(document_id="D", source_handles=("A", "B"), signed_distance=-5, current_layer="CUR")
    )
    assert {item.target_layer for item in plan.operations} == {"CUR"}
    with pytest.raises(ValueError, match="non-zero"):
        OffsetCurrentLayerRequest(document_id="D", source_handles=("A",), signed_distance=0, current_layer="CUR")


def test_ot_requires_two_explicit_distinct_tolerance_offsets() -> None:
    plan = plan_offset_tolerance(
        ToleranceOffsetRequest(
            document_id="D", source_handles=("A",), lower_signed_distance=-2, upper_signed_distance=3
        )
    )
    assert [item.signed_distance for item in plan.operations] == [-2, 3]
    with pytest.raises(ValueError, match="must differ"):
        ToleranceOffsetRequest(
            document_id="D", source_handles=("A",), lower_signed_distance=2, upper_signed_distance=2
        )


def test_rdc_is_deterministic_and_bounded() -> None:
    request = RandomCopyRequest(
        document_id="D",
        source_handles=("A", "B"),
        bounds=BoundingBox3D(minimum=Point3D(x=0, y=10), maximum=Point3D(x=100, y=20)),
        copy_count=4,
        seed="fixture-seed",
        minimum_rotation_degrees=-10,
        maximum_rotation_degrees=10,
    )
    first, second = plan_random_copy(request), plan_random_copy(request)
    assert first.placements == second.placements
    assert [item.source_handle for item in first.placements] == ["A", "B", "A", "B"]
    assert all(0 <= item.destination.x <= 100 and 10 <= item.destination.y <= 20 for item in first.placements)


def test_rm_uses_caller_supplied_center_per_target() -> None:
    request = RotateMultiRequest(
        document_id="D",
        targets=(RotationTarget(handle="A", center=Point3D(x=1, y=2)),),
        angle_degrees=90,
        keep_originals=False,
    )
    operation = plan_rotate_multi(request).operations[0]
    assert operation.center == Point3D(x=1, y=2)
    assert operation.angle_degrees == 90


def test_sb_validates_explicit_type_and_destination() -> None:
    plan = plan_solid_move_back(
        SolidMoveBackRequest(
            document_id="D",
            target_handles=("A",),
            entity_types={"a": "HATCH"},
            mode=DrawOrderMode.BEHIND_REFERENCE,
            reference_handle="R",
        )
    )
    assert plan.reference_handle == "R"
    with pytest.raises(ValueError, match="restricted"):
        SolidMoveBackRequest(
            document_id="D", target_handles=("A",), entity_types={"A": "LINE"}, mode=DrawOrderMode.BOTTOM
        )


def test_non_dry_run_requires_exact_canonical_fingerprint() -> None:
    draft = OffsetCurrentLayerRequest(
        document_id="D", source_handles=("A",), signed_distance=5, current_layer="CUR"
    )
    with pytest.raises(ValueError, match="exact approval fingerprint"):
        OffsetCurrentLayerRequest(
            document_id="D",
            source_handles=("A",),
            signed_distance=5,
            current_layer="CUR",
            dry_run=False,
            approval=Approval(approved=True, fingerprint="sha256:wrong"),
        )
    approved = OffsetCurrentLayerRequest(
        document_id="D",
        source_handles=("A",),
        signed_distance=5,
        current_layer="CUR",
        dry_run=False,
        approval=Approval(approved=True, fingerprint=draft.fingerprint()),
    )
    assert not approved.dry_run


def test_registers_six_read_only_tools() -> None:
    mcp = FastMCP("batch22a-test")
    register_headless_core_batch22a_tools(mcp)
    tools = asyncio.run(mcp.list_tools())
    assert len(tools) == 6
    assert all(tool.annotations and tool.annotations.readOnlyHint for tool in tools)
    assert all(tool.annotations and not tool.annotations.destructiveHint for tool in tools)
