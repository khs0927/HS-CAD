from __future__ import annotations

import asyncio

import pytest
from mcp.server.fastmcp import FastMCP

from xicad_mcp.headless_core_batch1 import Approval
from xicad_mcp.headless_core_batch30b import (
    AutoPlotRequest,
    DeletedEntityResult,
    DeletePlotBoxesRequest,
    ExactEntityResult,
    FileFormat,
    InsertBlocksRequest,
    InsertFileResult,
    InsertMode,
    MultiFileOrganizeRequest,
    OrganizedFileResult,
    PlotArtifactResult,
    PlotBoxConversionResult,
    PlotBoxCreateRequest,
    PlotBoxMultiMakeRequest,
    PlotFrameSnapshot,
    PlotSettingsSnapshot,
    SaveMode,
    VersionedEntitySnapshot,
    VersionedFileSnapshot,
    XrefDisposition,
    plan_auto_plot,
    plan_delete_plot_boxes,
    plan_insert_blocks,
    plan_multi_file_organize,
    plan_plot_box_create,
    plan_plot_box_multi_make,
    register_headless_core_batch30b_tools,
)

DIGEST_A = "sha256:" + "a" * 64
DIGEST_B = "sha256:" + "b" * 64


def file(path: str = "C:/in/A.dwg", *, opened: bool = False) -> VersionedFileSnapshot:
    return VersionedFileSnapshot(
        path=path,
        revision="f1",
        content_digest=DIGEST_A,
        format=FileFormat.DWG,
        is_saved=True,
        is_open=opened,
    )


def entity(result_id: str = "20", *, layer: str = "PLOT_BOX", owner: str = "Model") -> ExactEntityResult:
    return ExactEntityResult(
        result_id=result_id,
        result_revision="r2",
        entity_type="AcDbPolyline",
        owner=owner,
        layer=layer,
        state_digest=DIGEST_B,
    )


def snapshot(handle: str = "10", *, layer: str = "PLOT_BOX") -> VersionedEntitySnapshot:
    return VersionedEntitySnapshot(
        handle=handle,
        revision="r1",
        entity_type="AcDbPolyline",
        owner="Model",
        layer=layer,
        state_digest=DIGEST_A,
    )


def test_ib_binds_saved_files_and_current_dcl_modes_to_exact_results() -> None:
    source = file()
    result = InsertFileResult(
        source_path=source.path,
        source_revision=source.revision,
        exact_entities=(entity(layer="0"),),
        result_manifest_digest=DIGEST_B,
    )
    request = InsertBlocksRequest(
        document_id="D",
        files=(source,),
        insert_mode=InsertMode.XREF,
        xref_disposition=XrefDisposition.BIND,
        explode_inserted_drawings=False,
        redefine_same_name_blocks=True,
        order_policy="top_left_rows",
        items_per_row=10,
        horizontal_gap=5000,
        vertical_gap=5000,
        image_width=1000,
        exact_results=(result,),
        cad_platform="ZWCAD",
    )
    assert plan_insert_blocks(request).exact_results == (result,)
    with pytest.raises(ValueError, match="exactly for xref"):
        InsertBlocksRequest.model_validate({**request.model_dump(), "xref_disposition": None})
    with pytest.raises(ValueError, match="only saved"):
        InsertBlocksRequest.model_validate(
            {**request.model_dump(), "files": [{**source.model_dump(), "is_saved": False}]}
        )


def test_ib_help_platform_guard_blocks_pdf_vector_on_zwcad() -> None:
    source = file("C:/in/A.pdf").model_copy(update={"format": FileFormat.PDF})
    result = InsertFileResult(
        source_path=source.path,
        source_revision="f1",
        exact_entities=(entity(layer="PDF"),),
        result_manifest_digest=DIGEST_B,
    )
    data = dict(
        document_id="D",
        files=(source,),
        insert_mode=InsertMode.PDF_VECTOR,
        explode_inserted_drawings=False,
        redefine_same_name_blocks=False,
        order_policy="source_pages",
        items_per_row=10,
        horizontal_gap=0,
        vertical_gap=0,
        image_width=1000,
        exact_results=(result,),
        cad_platform="ZWCAD",
    )
    with pytest.raises(ValueError, match="unavailable"):
        InsertBlocksRequest(**data)


def test_msl_preserves_help_save_modes_and_excludes_open_list_files() -> None:
    source = file()
    result = OrganizedFileResult(
        source_path=source.path,
        source_revision="f1",
        destination_path="C:/out/A.dwg",
        output_revision="f2",
        output_digest=DIGEST_B,
        persisted=True,
    )
    request = MultiFileOrganizeRequest(
        document_id="D",
        files=(source,),
        save_mode=SaveMode.SAVE_AS,
        save_as_folder="C:/out",
        current_file_only=False,
        script_commands=("(setvar 'ImageFrame 2)",),
        operation_manifest_digest=DIGEST_A,
        exact_results=(result,),
    )
    assert plan_multi_file_organize(request).save_mode == SaveMode.SAVE_AS
    with pytest.raises(ValueError, match="excludes open"):
        MultiFileOrganizeRequest.model_validate(
            {**request.model_dump(), "files": [{**source.model_dump(), "is_open": True}]}
        )
    with pytest.raises(ValueError, match="required exactly"):
        MultiFileOrganizeRequest.model_validate({**request.model_dump(), "save_as_folder": None})


def test_pb_and_pbd_require_plot_box_layers_and_complete_deletions() -> None:
    create = PlotBoxCreateRequest(
        document_id="D",
        target_owner="Model",
        target_owner_revision="m1",
        exact_plot_box=entity(),
    )
    assert plan_plot_box_create(create).result.layer == "PLOT_BOX"
    with pytest.raises(ValueError, match=r"PLOT_BOX\*"):
        plan_plot_box_create(create.model_copy(update={"exact_plot_box": entity(layer="0")}))

    source = snapshot()
    deleted = DeletedEntityResult(source_handle="10", source_revision="r1", deleted=True)
    request = DeletePlotBoxesRequest(
        document_id="D",
        owner="Model",
        owner_revision="m1",
        complete_plot_box_handles=("10",),
        plot_boxes=(source,),
        exact_results=(deleted,),
    )
    assert plan_delete_plot_boxes(request).results == (deleted,)
    with pytest.raises(ValueError, match="complete unique"):
        DeletePlotBoxesRequest.model_validate({**request.model_dump(), "complete_plot_box_handles": ["20"]})


def test_pbm_requires_polyline_sources_and_explicit_plot_box_results() -> None:
    source = snapshot(layer="FRAME")
    result = PlotBoxConversionResult(
        source_handle="10",
        source_revision="r1",
        source_retained=True,
        exact_plot_box=entity(),
    )
    request = PlotBoxMultiMakeRequest(document_id="D", poly_boxes=(source,), exact_results=(result,))
    assert plan_plot_box_multi_make(request).results[0].source_retained
    with pytest.raises(ValueError, match=r"PLOT_BOX\*"):
        PlotBoxMultiMakeRequest.model_validate(
            {
                **request.model_dump(),
                "exact_results": [{**result.model_dump(), "exact_plot_box": entity(layer="0")}],
            }
        )


def test_ppp_binds_artifacts_to_frame_and_settings_revisions_without_io() -> None:
    frame = PlotFrameSnapshot(
        frame_id="F1",
        revision="fr1",
        geometry_digest=DIGEST_A,
        source_document_path="C:/in/A.dwg",
        source_document_revision="d1",
    )
    settings = PlotSettingsSnapshot(
        config_revision="p1",
        config_digest=DIGEST_A,
        plotter_name="ZWCAD PDF",
        paper_name="ISO A3",
        style_sheet="mono.ctb",
        copies=1,
        scale_policy="fit",
        rotation_policy="auto",
        location_policy="center",
        output_policy="pdf_file",
    )
    result = PlotArtifactResult(
        frame_id="F1",
        frame_revision="fr1",
        settings_revision="p1",
        output_path="C:/out/A.pdf",
        artifact_digest=DIGEST_B,
        plot_manifest_digest=DIGEST_B,
    )
    request = AutoPlotRequest(document_id="D", frames=(frame,), settings=settings, exact_results=(result,))
    assert plan_auto_plot(request).results == (result,)
    with pytest.raises(ValueError, match="exact settings revision"):
        AutoPlotRequest.model_validate(
            {**request.model_dump(), "exact_results": [{**result.model_dump(), "settings_revision": "old"}]}
        )


def test_canonical_approval_and_six_read_only_tools() -> None:
    request = PlotBoxCreateRequest(
        document_id="D",
        target_owner="Model",
        target_owner_revision="m1",
        exact_plot_box=entity(),
    )
    with pytest.raises(ValueError, match="exact approval"):
        PlotBoxCreateRequest.model_validate(
            request.model_copy(
                update={"dry_run": False, "approval": Approval(approved=True, fingerprint="sha256:wrong")}
            ).model_dump()
        )
    approved = PlotBoxCreateRequest.model_validate(
        request.model_copy(
            update={
                "dry_run": False,
                "approval": Approval(approved=True, fingerprint=request.fingerprint()),
            }
        ).model_dump()
    )
    assert not plan_plot_box_create(approved).dry_run

    mcp = FastMCP("batch30b")
    register_headless_core_batch30b_tools(mcp)
    tools = asyncio.run(mcp.list_tools())
    assert {tool.name for tool in tools} == {
        "xicad_plan_ib",
        "xicad_plan_msl",
        "xicad_plan_pb",
        "xicad_plan_pbd",
        "xicad_plan_pbm",
        "xicad_plan_ppp",
    }
    assert all(tool.annotations and tool.annotations.readOnlyHint for tool in tools)
    assert all(tool.annotations and not tool.annotations.destructiveHint for tool in tools)
