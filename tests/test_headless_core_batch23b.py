from __future__ import annotations

import asyncio

import pytest
from mcp.server.fastmcp import FastMCP

from xicad_mcp.headless_core_batch1 import Approval, Point3D
from xicad_mcp.headless_core_batch23b import (
    AllocationSource,
    AreaElementsRequest,
    AreaSnapshot,
    BlockReplacement,
    BuildingDistanceRequest,
    BuildingDistanceSnapshot,
    BunAreaRequest,
    DistanceVerdict,
    EntitySnapshot,
    FrameRotation,
    MapAreaRequest,
    ObjectToBlockMode,
    ObjectToBlockRequest,
    ProposedAllocationRecord,
    ProposedAreaLabel,
    ProposedAreaTriangle,
    ProposedDistanceReview,
    ZoomOperation,
    ZoomRecordScope,
    ZoomRegionSnapshot,
    ZoomRememberRequest,
    plan_area_elements,
    plan_building_distance,
    plan_bun_area,
    plan_map_area,
    plan_object_to_block,
    plan_zoom_remember,
    register_headless_core_batch23b_tools,
)


def point(x: float, y: float = 0, z: float = 0) -> Point3D:
    return Point3D(x=x, y=y, z=z)


def test_tob_uses_recovered_dcl_mode_and_only_exact_replacement_geometry() -> None:
    request = ObjectToBlockRequest(
        document_id="D",
        mode=ObjectToBlockMode.PLOT_BOX_TO_FRAME_BLOCK,
        source_entities=(EntitySnapshot(handle="A", entity_type="LWPOLYLINE", layer="FRAME"),),
        exact_replacements=(
            BlockReplacement(
                source_handles=("A",),
                block_name="A1_FRAME",
                insertion_point=point(10, 20),
                scale_x=2,
                scale_y=2,
                scale_z=1,
                rotation_degrees=90,
                layer="FRAME",
            ),
        ),
        delete_originals=True,
        link_scale=True,
        link_rotation=True,
        frame_rotation=FrameRotation.CLOCKWISE,
    )
    plan = plan_object_to_block(request)
    assert plan.creates[0].block_name == "A1_FRAME"
    assert plan.delete_handles == ("A",)
    assert plan.request_fingerprint == request.fingerprint()


def test_tob_rejects_unconsumed_source_and_implicit_frame_rotation() -> None:
    replacement = BlockReplacement(
        source_handles=("A",),
        block_name="B",
        insertion_point=point(0),
        scale_x=1,
        scale_y=1,
        scale_z=1,
        rotation_degrees=0,
        layer="0",
    )
    with pytest.raises(ValueError, match="consume every source"):
        ObjectToBlockRequest(
            document_id="D",
            mode=ObjectToBlockMode.OBJECT_TO_BLOCK,
            source_entities=(
                EntitySnapshot(handle="A", entity_type="LINE", layer="0"),
                EntitySnapshot(handle="B", entity_type="LINE", layer="0"),
            ),
            exact_replacements=(replacement,),
            delete_originals=False,
            link_scale=False,
            link_rotation=False,
        )
    with pytest.raises(ValueError, match="requires an explicit"):
        ObjectToBlockRequest(
            document_id="D",
            mode=ObjectToBlockMode.PLOT_BOX_TO_FRAME_BLOCK,
            source_entities=(EntitySnapshot(handle="A", entity_type="LINE", layer="0"),),
            exact_replacements=(replacement,),
            delete_originals=False,
            link_scale=False,
            link_rotation=False,
        )


def test_zr_requires_exact_slot_scope_region_and_persistence_revision() -> None:
    request = ZoomRememberRequest(
        document_id="D",
        operation=ZoomOperation.RESTORE,
        scope=ZoomRecordScope.EACH_DRAWING,
        slot=9,
        persistence_key="D:/project/Drawing1.dwg",
        persisted_revision="sha256:stored-view",
        exact_region=ZoomRegionSnapshot(lower_left=point(0, 10), upper_right=point(100, 210)),
    )
    plan = plan_zoom_remember(request)
    assert plan.slot == 9 and plan.exact_region.upper_right == point(100, 210)
    with pytest.raises(ValueError, match="below upper-right"):
        ZoomRegionSnapshot(lower_left=point(10, 10), upper_right=point(0, 20))


def test_ae_requires_one_exact_label_matching_each_area_snapshot() -> None:
    source = AreaSnapshot(handle="P1", area=24, geometry_revision="r1")
    label = ProposedAreaLabel(
        source_handle="P1",
        reported_area=24,
        text="24.00 m2",
        insertion_point=point(5, 5),
        layer="AREA",
        text_height=2.5,
    )
    assert plan_area_elements(
        AreaElementsRequest(document_id="D", source_areas=(source,), exact_labels=(label,))
    ).creates == (label,)
    with pytest.raises(ValueError, match="reported area"):
        AreaElementsRequest(
            document_id="D",
            source_areas=(source,),
            exact_labels=(label.model_copy(update={"reported_area": 25}),),
        )


def test_ahm_accepts_only_explicit_area_conserving_triangles() -> None:
    boundary = AreaSnapshot(handle="P", area=50, geometry_revision="r1")
    triangle = ProposedAreaTriangle(source_handle="P", a=point(0, 0), b=point(10, 0), c=point(0, 10), layer="AREA")
    plan = plan_map_area(MapAreaRequest(document_id="D", boundary=boundary, exact_triangles=(triangle,)))
    assert plan.computed_triangle_area == 50
    with pytest.raises(ValueError, match="area sum"):
        MapAreaRequest(
            document_id="D",
            boundary=boundary.model_copy(update={"area": 60}),
            exact_triangles=(triangle,),
        )


def test_ba_uses_declared_proportional_policy_and_validates_records() -> None:
    recipients = (
        AllocationSource(recipient_id="A", exclusive_area=80, allocation_weight=1, geometry_revision="r1"),
        AllocationSource(recipient_id="B", exclusive_area=120, allocation_weight=3, geometry_revision="r2"),
    )
    records = (
        ProposedAllocationRecord(
            recipient_id="A",
            reported_shared_area=10,
            reported_total_area=90,
            text="A=90",
            insertion_point=point(0),
            layer="AREA",
        ),
        ProposedAllocationRecord(
            recipient_id="B",
            reported_shared_area=30,
            reported_total_area=150,
            text="B=150",
            insertion_point=point(10),
            layer="AREA",
        ),
    )
    plan = plan_bun_area(BunAreaRequest(document_id="D", recipients=recipients, shared_area=40, exact_records=records))
    assert plan.allocation_policy == "shared_area * recipient_weight / sum(weights)"
    with pytest.raises(ValueError, match="reported shared area"):
        BunAreaRequest(
            document_id="D",
            recipients=recipients,
            shared_area=40,
            exact_records=(records[0].model_copy(update={"reported_shared_area": 11}), records[1]),
        )


def test_cdb_computes_only_from_explicit_closest_points_and_threshold() -> None:
    snapshot = BuildingDistanceSnapshot(
        building_a_id="A",
        building_b_id="B",
        closest_point_a=point(0, 0),
        closest_point_b=point(3, 4),
        geometry_revision_a="r1",
        geometry_revision_b="r2",
    )
    review = ProposedDistanceReview(
        reported_distance=5,
        required_minimum=6,
        verdict=DistanceVerdict.FAIL,
        text="5.00 < 6.00",
        insertion_point=point(1, 2),
        layer="REVIEW",
    )
    assert (
        plan_building_distance(
            BuildingDistanceRequest(document_id="D", snapshot=snapshot, exact_review=review)
        ).measured_distance
        == 5
    )
    with pytest.raises(ValueError, match="verdict"):
        BuildingDistanceRequest(
            document_id="D",
            snapshot=snapshot,
            exact_review=review.model_copy(update={"verdict": DistanceVerdict.PASS}),
        )


def test_exact_fingerprint_and_six_read_only_tools() -> None:
    request = ZoomRememberRequest(
        document_id="D",
        operation=ZoomOperation.STORE,
        scope=ZoomRecordScope.ONE_SHARED,
        slot=1,
        persistence_key="global",
        persisted_revision="r1",
        exact_region=ZoomRegionSnapshot(lower_left=point(0, 0), upper_right=point(10, 10)),
    )
    invalid = request.model_copy(
        update={"dry_run": False, "approval": Approval(approved=True, fingerprint="sha256:wrong")}
    ).model_dump()
    with pytest.raises(ValueError, match="exact approval"):
        ZoomRememberRequest.model_validate(invalid)
    approved = ZoomRememberRequest.model_validate(
        request.model_copy(
            update={"dry_run": False, "approval": Approval(approved=True, fingerprint=request.fingerprint())}
        ).model_dump()
    )
    assert not plan_zoom_remember(approved).dry_run

    mcp = FastMCP("batch23b")
    register_headless_core_batch23b_tools(mcp)
    tools = asyncio.run(mcp.list_tools())
    assert {tool.name for tool in tools} == {
        "xicad_plan_tob",
        "xicad_plan_zr",
        "xicad_plan_ae",
        "xicad_plan_ahm",
        "xicad_plan_ba",
        "xicad_plan_cdb",
    }
    assert all(tool.annotations and tool.annotations.readOnlyHint for tool in tools)
    assert all(tool.annotations and not tool.annotations.destructiveHint for tool in tools)
