from __future__ import annotations

import asyncio

import pytest
from mcp.server.fastmcp import FastMCP

from xicad_mcp.headless_core_batch1 import Approval
from xicad_mcp.headless_core_batch32 import (
    BlockLibraryRequest,
    BreakMode,
    BreakMultiRequest,
    CadProduct,
    CenterlineRequest,
    CenterMode,
    EndConnectRequest,
    EndpointPair,
    EntitySnapshot,
    ExactChangeSet,
    ExactEntityResult,
    FileSnapshot,
    FilletLRequest,
    LibraryOperation,
    LibraryResult,
    MaskRequest,
    ObjectInfo,
    ObjectInfoRequest,
    OffsetCloseRequest,
    PlatformStatus,
    Point3D,
    ReferenceRotateRequest,
    ScaleListDeleteRequest,
    XSymbolRequest,
    plan_block_library,
    plan_break_multi,
    plan_centerline,
    plan_end_connect,
    plan_fillet_l,
    plan_mask,
    plan_object_info,
    plan_offset_close,
    plan_reference_rotate,
    plan_scale_list_delete,
    plan_x_symbol,
    register_headless_core_batch32_tools,
)

DIGEST_A = "sha256:" + "a" * 64
DIGEST_B = "sha256:" + "b" * 64


def entity(handle: str, revision: str = "r1", kind: str = "LINE") -> EntitySnapshot:
    return EntitySnapshot(
        handle=handle, revision=revision, entity_type=kind, state_digest=DIGEST_A
    )


def changes(*sources: EntitySnapshot, marker: str | None = None) -> ExactChangeSet:
    revisions = (marker,) if marker else tuple(item.revision for item in sources)
    return ExactChangeSet(
        source_revisions=revisions,
        created_or_updated=(
            ExactEntityResult(
                result_id="N1", entity_type="LWPOLYLINE", layer="A-ANNO", state_digest=DIGEST_B
            ),
        ),
        manifest_digest=DIGEST_B,
    )


def test_ce_models_dcl_settings_and_revision_bound_exact_geometry() -> None:
    sources = (entity("10"), entity("11", "r2"))
    request = CenterlineRequest(
        document_id="D",
        sources=sources,
        mode=CenterMode.PAIR,
        create_polyline=True,
        extension_length=200,
        maximum_recognition_distance=250,
        output_layer="CEN2",
        exact_changes=changes(*sources),
    )
    plan = plan_centerline(request)
    assert (plan.command_alias, plan.current_alias) == ("CE", "CEN")
    with pytest.raises(ValueError, match="exactly two"):
        CenterlineRequest.model_validate({**request.model_dump(), "sources": sources[:1]})
    with pytest.raises(ValueError, match="every source revision"):
        CenterlineRequest.model_validate(
            {
                **request.model_dump(),
                "exact_changes": {
                    **request.exact_changes.model_dump(),
                    "source_revisions": ["wrong", "r2"],
                },
            }
        )


def test_bbb_preserves_all_three_documented_break_modes() -> None:
    source = entity("10")
    one = BreakMultiRequest(
        document_id="D",
        sources=(source,),
        mode=BreakMode.ONE_POINT,
        break_points=(Point3D(x=1, y=2),),
        exact_changes=changes(source),
    )
    assert plan_break_multi(one).current_alias == "B"
    with pytest.raises(ValueError, match="exactly two points"):
        BreakMultiRequest.model_validate({**one.model_dump(), "mode": "two_point"})
    with pytest.raises(ValueError, match="exactly one source"):
        BreakMultiRequest.model_validate(
            {
                **one.model_dump(),
                "sources": [source.model_dump(), entity("11").model_dump()],
                "mode": "multiple_points_one_curve",
                "break_points": [{"x": 1, "y": 2}, {"x": 3, "y": 4}],
                "exact_changes": changes(source, entity("11")).model_dump(),
            }
        )


def test_ff_and_wq_require_explicit_topology_results() -> None:
    sources = (entity("10"), entity("11", "r2"), entity("12", "r3"))
    ff = FilletLRequest(
        document_id="D",
        sources=sources,
        selection_corner_a=Point3D(x=0, y=0),
        selection_corner_b=Point3D(x=10, y=10),
        excluded_centerline_handles=("12",),
        exact_changes=changes(*sources),
    )
    assert plan_fillet_l(ff).current_alias == "FL"
    with pytest.raises(ValueError, match="belong"):
        FilletLRequest.model_validate(
            {**ff.model_dump(), "excluded_centerline_handles": ["missing"]}
        )

    wq = OffsetCloseRequest(
        document_id="D",
        source=sources[0],
        offset_distance=100,
        side_point=Point3D(x=0, y=5),
        output_layer="A-METAL",
        exact_changes=changes(sources[0]),
    )
    assert plan_offset_close(wq).current_alias == "OC"
    with pytest.raises(ValueError, match="non-zero"):
        OffsetCloseRequest.model_validate({**wq.model_dump(), "offset_distance": 0})


def test_we_validates_documented_distance_and_source_endpoint_pairs() -> None:
    sources = (entity("10"), entity("11", "r2"))
    pair = EndpointPair(
        first_handle="10",
        first_point=Point3D(x=0, y=0),
        second_handle="11",
        second_point=Point3D(x=0, y=200),
        measured_distance=200,
    )
    request = EndConnectRequest(
        document_id="D",
        sources=sources,
        maximum_distance=210,
        require_parallel=True,
        endpoint_pairs=(pair,),
        exact_changes=changes(*sources),
    )
    assert plan_end_connect(request).current_alias == "PET"
    with pytest.raises(ValueError, match="exceeds"):
        EndConnectRequest.model_validate({**request.model_dump(), "maximum_distance": 100})


def test_xx_and_mk_keep_image_and_mask_gaps_explicit() -> None:
    xx = XSymbolRequest(
        document_id="D",
        first_corner=Point3D(x=0, y=0),
        opposite_corner=Point3D(x=10, y=20),
        output_layer="A-VOID",
        exact_changes=changes(marker="drawing-input"),
    )
    assert plan_x_symbol(xx).current_alias == "X"
    assert any("image" in gap for gap in plan_x_symbol(xx).semantic_gaps)

    text = entity("20", kind="AcDbMText")
    mk = MaskRequest(
        document_id="D",
        sources=(text,),
        enabled=True,
        border_offset_factor=1.5,
        exact_changes=changes(text),
    )
    assert plan_mask(mk).current_alias == "MSK"
    with pytest.raises(ValueError, match="multiline text"):
        MaskRequest.model_validate(
            {**mk.model_dump(), "sources": [entity("21", kind="TEXT").model_dump()]}
        )


def test_q11_models_file_operations_without_performing_io() -> None:
    source = FileSnapshot(path="C:/xicad/xiLib/door.dwg", revision="f1", content_digest=DIGEST_A)
    result = LibraryResult(
        source_revisions=("f1",),
        result_files=(),
        inserted_entities=(
            ExactEntityResult(
                result_id="B1", entity_type="INSERT", layer="A-DOOR", state_digest=DIGEST_B
            ),
        ),
        manifest_digest=DIGEST_B,
    )
    request = BlockLibraryRequest(
        document_id="D",
        operation=LibraryOperation.INSERT,
        library_root="C:/xicad/xiLib",
        sources=(source,),
        insertion_point=Point3D(x=1, y=2),
        scale=100,
        rotation_degrees=0,
        output_layer="A-DOOR",
        exact_result=result,
    )
    assert plan_block_library(request).current_alias == "Q1"
    with pytest.raises(ValueError, match="point, scale"):
        BlockLibraryRequest.model_validate({**request.model_dump(), "insertion_point": None})


def test_rr_and_lii_preserve_renamed_symbols_and_exact_results() -> None:
    source = entity("10")
    rr = ReferenceRotateRequest(
        document_id="D",
        sources=(source,),
        base_point=Point3D(x=0, y=0),
        reference_start=Point3D(x=10, y=0),
        reference_end=Point3D(x=20, y=0),
        destination_start=Point3D(x=100, y=100),
        destination_end=Point3D(x=100, y=200),
        exact_changes=changes(source),
    )
    rr_plan = plan_reference_rotate(rr)
    assert (rr_plan.legacy_symbol, rr_plan.current_symbol) == ("xiRR", "xiRefRotate")

    info = ObjectInfo(
        selected_handle="10",
        container_path=("Door", "Building"),
        external_reference_path="C:/xref/site.dwg",
        effective_color="1",
        layer_color="7",
        effective_linetype="DASHED",
        layer_linetype="CONTINUOUS",
        result_digest=DIGEST_B,
    )
    lii = ObjectInfoRequest(
        document_id="D", source=source, nested_pick_path=info.container_path, exact_info=info
    )
    assert plan_object_info(lii).current_symbol == "xiListInBlk"
    with pytest.raises(ValueError, match="selected source"):
        ObjectInfoRequest.model_validate(
            {
                **lii.model_dump(),
                "exact_info": {**info.model_dump(), "selected_handle": "wrong"},
            }
        )


def test_sld_windows_product_guard_never_claims_zwcad_support() -> None:
    request = ScaleListDeleteRequest(
        document_id="D",
        os_family="Windows",
        cad_product=CadProduct.ZWCAD,
        cad_version="2026",
        source_revision="d1",
        scale_names=("1:50", "1:100"),
    )
    plan = plan_scale_list_delete(request)
    assert plan.platform_status is PlatformStatus.BLOCKED_UNSUPPORTED
    assert not plan.production_usable
    with pytest.raises(ValueError, match="unsupported on ZWCAD"):
        ScaleListDeleteRequest.model_validate(
            {
                **request.model_dump(),
                "dry_run": False,
                "approval": Approval(
                    approved=True, fingerprint=request.fingerprint()
                ).model_dump(),
            }
        )
    with pytest.raises(ValueError, match="Windows"):
        ScaleListDeleteRequest.model_validate({**request.model_dump(), "os_family": "Linux"})


def test_canonical_approval_and_eleven_read_only_tools() -> None:
    source = entity("10")
    request = OffsetCloseRequest(
        document_id="D",
        source=source,
        offset_distance=10,
        side_point=Point3D(x=0, y=1),
        output_layer="0",
        exact_changes=changes(source),
    )
    with pytest.raises(ValueError, match="exact approval"):
        OffsetCloseRequest.model_validate(
            {
                **request.model_dump(),
                "dry_run": False,
                "approval": Approval(approved=True, fingerprint="sha256:wrong").model_dump(),
            }
        )
    approved = OffsetCloseRequest.model_validate(
        {
            **request.model_dump(),
            "dry_run": False,
            "approval": Approval(
                approved=True, fingerprint=request.fingerprint()
            ).model_dump(),
        }
    )
    assert not plan_offset_close(approved).dry_run

    mcp = FastMCP("batch32")
    register_headless_core_batch32_tools(mcp)
    tools = asyncio.run(mcp.list_tools())
    assert len(tools) == 11
    assert all(tool.annotations and tool.annotations.readOnlyHint for tool in tools)
    assert all(tool.annotations and not tool.annotations.destructiveHint for tool in tools)
