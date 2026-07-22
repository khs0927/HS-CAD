from __future__ import annotations

import asyncio

import pytest
from mcp.server.fastmcp import FastMCP

from xicad_mcp.headless_core_batch1 import Approval, Point3D
from xicad_mcp.headless_core_batch28b import (
    AttributedBlockSnapshot,
    AttributeSnapshot,
    BlockChangeMode,
    BlockFileMethod,
    DocumentSnapshot,
    EntitySnapshot,
    ExplicitDocumentResult,
    ExplodeAttributesRetainingTextRequest,
    ExplodedBlockResult,
    InsertKind,
    MultiFileBlockChangeRequest,
    MultiFileBlockOptions,
    MultiFileXrefChangeRequest,
    MultiFileXrefOptions,
    MultiInsertSnapshot,
    MultiInsertToBlocksRequest,
    MultiXclipRequest,
    OrdinaryBlockResult,
    ReferenceKind,
    ReferenceScope,
    RetainedAttributeText,
    WblockExportJob,
    WblockExportRequest,
    XclipReferenceSnapshot,
    XclipResult,
    XrefMethod,
    plan_explode_attributes_retaining_text,
    plan_multi_file_block_change,
    plan_multi_file_xref_change,
    plan_multi_insert_to_blocks,
    plan_multi_xclip,
    plan_wblock_export,
    register_headless_core_batch28b_tools,
)

DIGEST_A = "sha256:" + "a" * 64
DIGEST_B = "sha256:" + "b" * 64


def point(x: float, y: float = 0) -> Point3D:
    return Point3D(x=x, y=y, z=0)


def entity(handle: str, revision: str = "r1", kind: str = "AcDbBlockReference") -> EntitySnapshot:
    return EntitySnapshot(handle=handle, revision=revision, entity_type=kind, state_digest=DIGEST_A)


def document(uri: str = "C:/in/a.dwg", revision: str = "d1") -> DocumentSnapshot:
    return DocumentSnapshot(source_uri=uri, revision=revision, content_digest=DIGEST_A)


def document_result(uri: str = "C:/in/a.dwg", revision: str = "d1") -> ExplicitDocumentResult:
    return ExplicitDocumentResult(
        source_uri=uri,
        source_revision=revision,
        expected_content_digest=DIGEST_B,
        result_manifest_digest=DIGEST_B,
    )


def test_ear_requires_one_retained_text_per_versioned_attribute() -> None:
    source = AttributedBlockSnapshot(
        reference=entity("10"),
        block_name="TAG",
        attributes=(AttributeSnapshot(handle="11", tag="NO", text="101", state_digest=DIGEST_A),),
    )
    result = ExplodedBlockResult(
        source_handle="10",
        source_revision="r1",
        exact_entities=(entity("20", "r2", "AcDbLine"),),
        retained_attribute_texts=(
            RetainedAttributeText(source_attribute_handle="11", exact_text_entity=entity("21", "r2", "AcDbText")),
        ),
    )
    request = ExplodeAttributesRetainingTextRequest(document_id="D", blocks=(source,), exact_results=(result,))
    assert plan_explode_attributes_retaining_text(request).results == (result,)
    with pytest.raises(ValueError, match="at least 1"):
        ExplodeAttributesRetainingTextRequest.model_validate(
            {**request.model_dump(), "exact_results": [{**result.model_dump(), "retained_attribute_texts": []}]}
        )


def test_m2b_enforces_array_cardinality_and_revision() -> None:
    source = MultiInsertSnapshot(
        source=entity("10"), block_name="CHAIR", rows=2, columns=2, row_spacing=10, column_spacing=20
    )
    result = OrdinaryBlockResult(
        source_handle="10",
        source_revision="r1",
        exact_references=tuple(entity(str(index), "r2") for index in range(20, 24)),
    )
    request = MultiInsertToBlocksRequest(document_id="D", multi_inserts=(source,), exact_results=(result,))
    assert len(plan_multi_insert_to_blocks(request).results[0].exact_references) == 4
    with pytest.raises(ValueError, match="rows multiplied"):
        MultiInsertToBlocksRequest.model_validate(
            {
                **request.model_dump(),
                "exact_results": [{**result.model_dump(), "exact_references": result.exact_references[:2]}],
            }
        )


def test_mfb_preserves_dcl_modes_but_performs_no_file_io() -> None:
    options = MultiFileBlockOptions(
        method=BlockFileMethod.INSERT,
        exclude_locked_layers=True,
        purge_after_replace_or_delete=False,
        insert_kind=InsertKind.BLOCK,
        insert_source_uri="C:/lib/chair.dwg",
        insert_source_digest=DIGEST_A,
        insert_scale=2,
        insert_point=point(100, 200),
        move_inserted_to_back=True,
    )
    request = MultiFileBlockChangeRequest(
        document_id="D", documents=(document(),), options=options, exact_results=(document_result(),)
    )
    plan = plan_multi_file_block_change(request)
    assert plan.options.insert_kind == InsertKind.BLOCK
    assert not plan.cad_mutation_tool_exposed
    with pytest.raises(ValueError, match="change method requires"):
        MultiFileBlockOptions(
            method=BlockFileMethod.CHANGE,
            exclude_locked_layers=False,
            purge_after_replace_or_delete=False,
        )


def test_mfb_results_are_complete_and_revision_bound() -> None:
    options = MultiFileBlockOptions(
        method=BlockFileMethod.CHANGE,
        change_mode=BlockChangeMode.REPLACE_INTERNAL,
        old_block_name="OLD",
        new_block_name_or_uri="NEW",
        exclude_locked_layers=False,
        purge_after_replace_or_delete=True,
    )
    with pytest.raises(ValueError, match="exact source revision"):
        MultiFileBlockChangeRequest(
            document_id="D",
            documents=(document(),),
            options=options,
            exact_results=(document_result(revision="wrong"),),
        )


def test_mfx_enforces_dcl_scope_and_content_addressed_repath() -> None:
    options = MultiFileXrefOptions(
        method=XrefMethod.REPATH_ONE,
        reference_kinds=frozenset({ReferenceKind.DWG, ReferenceKind.PDF}),
        exclude_locked_layers=True,
        do_not_save_after_work=True,
        scope=ReferenceScope.INCLUDE_ONLY,
        selected_reference_names=("SITE",),
        source_uri="C:/refs/site.dwg",
        source_digest=DIGEST_A,
        reference_name="SITE",
    )
    request = MultiFileXrefChangeRequest(
        document_id="D", documents=(document(),), options=options, exact_results=(document_result(),)
    )
    assert plan_multi_file_xref_change(request).options.do_not_save_after_work
    with pytest.raises(ValueError, match="does not accept"):
        MultiFileXrefOptions.model_validate({**options.model_dump(), "scope": "all"})


def test_mx_requires_complete_versioned_boundary_results() -> None:
    source = XclipReferenceSnapshot(reference=entity("10"), existing_boundary_digest=None)
    result = XclipResult(
        source_handle="10",
        source_revision="r1",
        exact_boundary=(point(0), point(10), point(10, 10)),
        expected_boundary_digest=DIGEST_B,
    )
    request = MultiXclipRequest(document_id="D", references=(source,), exact_results=(result,))
    assert len(plan_multi_xclip(request).results[0].exact_boundary) == 3
    with pytest.raises(ValueError, match="exact source revision"):
        MultiXclipRequest.model_validate(
            {**request.model_dump(), "exact_results": [{**result.model_dump(), "source_revision": "wrong"}]}
        )


def test_qwb_binds_selection_and_expected_digest_without_exporting() -> None:
    source = document(revision="d7")
    job = WblockExportJob(
        source_revision="d7",
        selected_handles=("10",),
        base_point=point(0),
        destination_uri="C:/out/part.dwg",
        overwrite=False,
        expected_content_digest=DIGEST_B,
    )
    request = WblockExportRequest(
        document_id="D", source_document=source, available_entities=(entity("10"),), exact_job=job
    )
    plan = plan_wblock_export(request)
    assert plan.job.expected_content_digest == DIGEST_B
    assert not plan.production_usable
    with pytest.raises(ValueError, match="must exist"):
        WblockExportRequest.model_validate(
            {**request.model_dump(), "exact_job": {**job.model_dump(), "selected_handles": ["404"]}}
        )


def test_approval_and_six_read_only_tool_annotations() -> None:
    source = document(revision="d7")
    job = WblockExportJob(
        source_revision="d7",
        selected_handles=("10",),
        base_point=point(0),
        destination_uri="C:/out/part.dwg",
        overwrite=False,
        expected_content_digest=DIGEST_B,
    )
    request = WblockExportRequest(
        document_id="D", source_document=source, available_entities=(entity("10"),), exact_job=job
    )
    with pytest.raises(ValueError, match="exact approval"):
        WblockExportRequest.model_validate(
            request.model_copy(
                update={"dry_run": False, "approval": Approval(approved=True, fingerprint="sha256:wrong")}
            ).model_dump()
        )
    approved = WblockExportRequest.model_validate(
        request.model_copy(
            update={"dry_run": False, "approval": Approval(approved=True, fingerprint=request.fingerprint())}
        ).model_dump()
    )
    assert not plan_wblock_export(approved).dry_run

    mcp = FastMCP("batch28b")
    register_headless_core_batch28b_tools(mcp)
    tools = asyncio.run(mcp.list_tools())
    assert {tool.name for tool in tools} == {
        "xicad_plan_ear",
        "xicad_plan_m2b",
        "xicad_plan_mfb",
        "xicad_plan_mfx",
        "xicad_plan_mx",
        "xicad_plan_qwb",
    }
    assert all(tool.annotations and tool.annotations.readOnlyHint for tool in tools)
    assert all(tool.annotations and not tool.annotations.destructiveHint for tool in tools)
