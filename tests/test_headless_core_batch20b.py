from __future__ import annotations

import asyncio

import pytest
from mcp.server.fastmcp import FastMCP

from xicad_mcp.headless_core_batch1 import Approval, Point3D
from xicad_mcp.headless_core_batch20b import (
    Axis,
    CopyRotateRequest,
    CopyToCurrentLayerRequest,
    CopyToNewLayerRequest,
    DynamicArrayRequest,
    ExplicitCopy,
    LayerDefinition,
    LinearArrayRequest,
    PolarArrayRequest,
    plan_copy_rotate,
    plan_copy_to_current_layer,
    plan_copy_to_new_layer,
    plan_dynamic_array,
    plan_linear_array,
    plan_polar_array,
    register_headless_core_batch20b_tools,
)

IDENTITY = ((1.0, 0.0, 0.0, 0.0), (0.0, 1.0, 0.0, 0.0), (0.0, 0.0, 1.0, 0.0), (0.0, 0.0, 0.0, 1.0))


def test_ard_accepts_only_explicit_affine_instances() -> None:
    request = DynamicArrayRequest(
        document_id="D", source_handles=("A",), copies=(ExplicitCopy(source_handle="A", transform=IDENTITY),)
    )
    plan = plan_dynamic_array(request)
    assert plan.command_alias == "ARD" and plan.copies[0].transform == IDENTITY
    non_affine = (*IDENTITY[:3], (0.0, 0.0, 0.0, 2.0))
    with pytest.raises(ValueError, match="affine"):
        ExplicitCopy(source_handle="A", transform=non_affine)


def test_arp_generates_deterministic_z_axis_rotation() -> None:
    request = PolarArrayRequest(
        document_id="D",
        source_handles=("A",),
        center=Point3D(x=0, y=0),
        reference_point=Point3D(x=10, y=0),
        axis=Axis.Z,
        item_count=4,
        total_angle_degrees=360,
        rotate_items=True,
    )
    plan = plan_polar_array(request)
    assert len(plan.copies) == 3
    assert plan.copies[0].transform[0][0] == pytest.approx(0)
    assert plan.copies[0].transform[1][0] == pytest.approx(1)


def test_arv_normalizes_direction_and_skips_source_position() -> None:
    request = LinearArrayRequest(
        document_id="D", source_handles=("A",), direction=Point3D(x=3, y=4), item_count=3, spacing=10
    )
    plan = plan_linear_array(request)
    assert len(plan.copies) == 2
    assert plan.copies[0].transform[0][3] == pytest.approx(6)
    assert plan.copies[0].transform[1][3] == pytest.approx(8)


def test_cnl_creates_explicit_layer_and_assigns_copies() -> None:
    layer = LayerDefinition(name="NEW", color=3, linetype="Continuous", lineweight=25)
    request = CopyToNewLayerRequest(
        document_id="D", source_handles=("A", "B"), displacement=Point3D(x=5, y=6), new_layer=layer
    )
    plan = plan_copy_to_new_layer(request)
    assert plan.create_layer == layer
    assert {item.target_layer for item in plan.copies} == {"NEW"}


def test_cr_combines_copy_and_z_rotation() -> None:
    request = CopyRotateRequest(
        document_id="D",
        source_handles=("A",),
        base_point=Point3D(x=1, y=0),
        destination_point=Point3D(x=10, y=0),
        rotation_degrees=90,
    )
    matrix = plan_copy_rotate(request).copies[0].transform
    assert matrix[0][3] == pytest.approx(10)
    assert matrix[1][3] == pytest.approx(-1)


def test_ctl_captures_current_layer_in_fingerprint() -> None:
    request = CopyToCurrentLayerRequest(
        document_id="D", source_handles=("A",), displacement=Point3D(x=1, y=2), current_layer="CURRENT"
    )
    plan = plan_copy_to_current_layer(request)
    assert plan.copies[0].target_layer == "CURRENT"
    assert request.fingerprint() != request.model_copy(update={"current_layer": "OTHER"}).fingerprint()


def test_exact_fingerprint_required_for_execution() -> None:
    request = LinearArrayRequest(
        document_id="D", source_handles=("A",), direction=Point3D(x=1, y=0), item_count=2, spacing=5
    )
    payload = request.model_copy(
        update={"dry_run": False, "approval": Approval(approved=True, fingerprint="wrong")}
    ).model_dump()
    with pytest.raises(ValueError, match="exact approval"):
        LinearArrayRequest.model_validate(payload)
    payload["approval"] = Approval(approved=True, fingerprint=request.fingerprint()).model_dump()
    approved = LinearArrayRequest.model_validate(payload)
    assert not approved.dry_run


def test_tool_annotations_are_read_only() -> None:
    mcp = FastMCP("batch20b")
    register_headless_core_batch20b_tools(mcp)
    tools = asyncio.run(mcp.list_tools())
    assert {tool.name for tool in tools} == {
        "xicad_plan_ard",
        "xicad_plan_arp",
        "xicad_plan_arv",
        "xicad_plan_cnl",
        "xicad_plan_cr",
        "xicad_plan_ctl",
    }
    assert all(tool.annotations and tool.annotations.readOnlyHint for tool in tools)
    assert all(tool.annotations and not tool.annotations.destructiveHint for tool in tools)
