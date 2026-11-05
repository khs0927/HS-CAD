from __future__ import annotations

import asyncio

import pytest
from mcp.server.fastmcp import FastMCP

from xicad_mcp.headless_core_batch1 import Approval, Point3D
from xicad_mcp.headless_core_batch31a import (
    AxisChangeRequest,
    AxisMode,
    AxisResetRequest,
    CopyValueRequest,
    CurrentSetting,
    DocumentResult,
    DocumentSnapshot,
    ElevationMarkRequest,
    EntitySnapshot,
    ExactGeometryResult,
    FileArtifact,
    FrameExportResult,
    FrameSnapshot,
    HatchThicknessRequest,
    KitchenInlineRequest,
    PurgeAllRequest,
    PurgeOperation,
    SaveSeparateRequest,
    WorkingAxisResult,
    WorkingAxisSnapshot,
    plan_axis_change,
    plan_axis_reset,
    plan_copy_value,
    plan_elevation_mark,
    plan_hatch_thickness,
    plan_kitchen_inline,
    plan_purge_all,
    plan_save_separate,
    register_headless_core_batch31a_tools,
)

DIGEST_A = "sha256:" + "a" * 64
DIGEST_B = "sha256:" + "b" * 64


def geometry(result_id: str = "10") -> ExactGeometryResult:
    return ExactGeometryResult(
        result_id=result_id,
        result_revision="r2",
        entity_type="AcDbPolyline",
        state_digest=DIGEST_B,
    )


def test_pua_requires_unique_operations_and_revision_bound_result() -> None:
    source = DocumentSnapshot(revision="d1", state_digest=DIGEST_A)
    result = DocumentResult(
        source_revision="d1",
        result_revision="d2",
        result_digest=DIGEST_B,
        result_manifest_digest=DIGEST_B,
    )
    request = PurgeAllRequest(
        document_id="D",
        source=source,
        operations=(PurgeOperation.CAD_PURGE_ALL, PurgeOperation.EMPTY_TEXT),
        operation_manifest_digest=DIGEST_A,
        exact_result=result,
    )
    assert plan_purge_all(request).result == result
    with pytest.raises(ValueError, match="unique"):
        PurgeAllRequest.model_validate(
            {**request.model_dump(), "operations": ["empty_text", "empty_text"]}
        )
    with pytest.raises(ValueError, match="exact source revision"):
        PurgeAllRequest.model_validate(
            {
                **request.model_dump(),
                "exact_result": {**result.model_dump(), "source_revision": "old"},
            }
        )


def test_svs_requires_one_exact_artifact_per_versioned_frame() -> None:
    frame = FrameSnapshot(
        frame_id="F1", revision="f1", frame_block_name="A1_FRAME", geometry_digest=DIGEST_A
    )
    result = FrameExportResult(
        frame_id="F1",
        frame_revision="f1",
        exact_artifact=FileArtifact(
            path=r"C:\out\A-101.dwg", content_digest=DIGEST_B, byte_length=1200
        ),
        result_manifest_digest=DIGEST_B,
    )
    request = SaveSeparateRequest(
        document_id="D",
        source=DocumentSnapshot(revision="d1", state_digest=DIGEST_A),
        output_folder=r"C:\out",
        frames=(frame,),
        settings_manifest_digest=DIGEST_A,
        exact_results=(result,),
    )
    assert plan_save_separate(request).results == (result,)
    with pytest.raises(ValueError, match="declared output folder"):
        SaveSeparateRequest.model_validate(
            {
                **request.model_dump(),
                "exact_results": [
                    {
                        **result.model_dump(),
                        "exact_artifact": {
                            **result.exact_artifact.model_dump(),
                            "path": r"C:\other\A-101.dwg",
                        },
                    }
                ],
            }
        )


def test_a0_and_a1_validate_exact_snapang_state() -> None:
    source = WorkingAxisSnapshot(revision="s1", snap_angle_radians=0.5, state_digest=DIGEST_A)
    reset = WorkingAxisResult(
        source_revision="s1", result_revision="s2", snap_angle_radians=0, state_digest=DIGEST_B
    )
    assert plan_axis_reset(
        AxisResetRequest(document_id="D", source=source, exact_result=reset)
    ).result.snap_angle_radians == 0
    with pytest.raises(ValueError, match="reset SNAPANG"):
        AxisResetRequest(
            document_id="D",
            source=source,
            exact_result=reset.model_copy(update={"snap_angle_radians": 1.0}),
        )
    changed = reset.model_copy(update={"snap_angle_radians": 0.3})
    request = AxisChangeRequest(
        document_id="D",
        source=source,
        mode=AxisMode.SLOPE_PERCENT,
        input_value=10,
        exact_result=changed,
    )
    assert plan_axis_change(request).mode == AxisMode.SLOPE_PERCENT
    with pytest.raises(ValueError, match="numeric input"):
        AxisChangeRequest.model_validate({**request.model_dump(), "input_value": None})


def test_cv_enforces_official_entity_to_current_value_mapping() -> None:
    source = EntitySnapshot(
        handle="10", revision="r1", entity_type="hatch", state_digest=DIGEST_A
    )
    settings = tuple(
        CurrentSetting(name=name, exact_value=value)
        for name, value in (("HPName", "EARTH"), ("HPScale", "25"))
    )
    request = CopyValueRequest(
        document_id="D", source=source, exact_settings=settings, result_state_digest=DIGEST_B
    )
    assert len(plan_copy_value(request).settings) == 2
    with pytest.raises(ValueError, match="documented entity-type mapping"):
        CopyValueRequest.model_validate(
            {**request.model_dump(), "exact_settings": settings[:-1]}
        )


def test_elm_ht_and_kci_require_explicit_unique_geometry() -> None:
    elm = ElevationMarkRequest(
        document_id="D",
        layer="A-ANNO",
        text_style="STANDARD",
        prefix="EL.",
        text_height=250,
        decimal_places=2,
        first_display_value=" 1,000",
        insertion_points=(Point3D(x=0, y=0, z=0),),
        settings_revision="cfg1",
        exact_results=(geometry(),),
        result_manifest_digest=DIGEST_B,
    )
    assert plan_elevation_mark(elm).results[0].result_id == "10"
    ht = HatchThicknessRequest(
        document_id="D",
        first_point=Point3D(x=0, y=0, z=0),
        second_point=Point3D(x=1000, y=0, z=0),
        thickness=200,
        hatch_pattern="EARTH",
        hatch_scale=100,
        settings_revision="cfg1",
        exact_results=(geometry("20"),),
        result_manifest_digest=DIGEST_B,
    )
    assert plan_hatch_thickness(ht).results[0].result_id == "20"
    with pytest.raises(ValueError, match="distinct points"):
        HatchThicknessRequest.model_validate(
            {**ht.model_dump(), "second_point": ht.first_point.model_dump()}
        )
    kci = KitchenInlineRequest(
        document_id="D",
        points=(
            Point3D(x=0, y=0, z=0),
            Point3D(x=3000, y=0, z=0),
            Point3D(x=3000, y=600, z=0),
        ),
        include_refrigerator=True,
        settings_revision="cfg1",
        exact_results=(geometry("30"), geometry("31")),
        result_manifest_digest=DIGEST_B,
    )
    assert len(plan_kitchen_inline(kci).results) == 2
    with pytest.raises(ValueError, match="three distinct"):
        KitchenInlineRequest.model_validate(
            {**kci.model_dump(), "points": [kci.points[0].model_dump()] * 3}
        )


def test_canonical_approval_and_eight_read_only_tools() -> None:
    source = WorkingAxisSnapshot(revision="s1", snap_angle_radians=1, state_digest=DIGEST_A)
    result = WorkingAxisResult(
        source_revision="s1", result_revision="s2", snap_angle_radians=0, state_digest=DIGEST_B
    )
    request = AxisResetRequest(document_id="D", source=source, exact_result=result)
    with pytest.raises(ValueError, match="exact approval"):
        AxisResetRequest.model_validate(
            request.model_copy(
                update={
                    "dry_run": False,
                    "approval": Approval(approved=True, fingerprint="sha256:wrong"),
                }
            ).model_dump()
        )
    approved = AxisResetRequest.model_validate(
        request.model_copy(
            update={
                "dry_run": False,
                "approval": Approval(approved=True, fingerprint=request.fingerprint()),
            }
        ).model_dump()
    )
    assert not plan_axis_reset(approved).dry_run

    mcp = FastMCP("batch31a")
    register_headless_core_batch31a_tools(mcp)
    tools = asyncio.run(mcp.list_tools())
    assert {tool.name for tool in tools} == {
        "xicad_plan_pua",
        "xicad_plan_svs",
        "xicad_plan_a0",
        "xicad_plan_a1",
        "xicad_plan_cv",
        "xicad_plan_elm",
        "xicad_plan_ht",
        "xicad_plan_kci",
    }
    assert all(tool.annotations and tool.annotations.readOnlyHint for tool in tools)
    assert all(tool.annotations and not tool.annotations.destructiveHint for tool in tools)
