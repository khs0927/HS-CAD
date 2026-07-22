import asyncio

import pytest
from mcp.server.fastmcp import FastMCP

from xicad_mcp.headless_core_batch1 import Approval, Point3D
from xicad_mcp.headless_core_batch28a import (
    BlockDefinitionSnapshot,
    BlockQuantityOptions,
    BlockQuantityRequest,
    BlockReferenceSnapshot,
    ChangeBlockScaleRequest,
    CopyObjectsToXrefRequest,
    EntitySnapshot,
    ExactBlockDefinition,
    ExactBlockReference,
    ExactEntity,
    ExactOutputArtifact,
    MakeBlockInPlaceRequest,
    ProposedBlockReference,
    QuantityOutput,
    QuantityRow,
    RemoveBlockMembersRequest,
    RenameBlocksRequest,
    RenameResult,
    XrefFileSnapshot,
    plan_block_quantity,
    plan_change_block_scale,
    plan_copy_objects_to_xref,
    plan_make_block_in_place,
    plan_remove_block_members,
    plan_rename_blocks,
    register_headless_core_batch28a_tools,
)

DIGEST_A = "sha256:" + "a" * 64
DIGEST_B = "sha256:" + "b" * 64


def point(x: float = 0) -> Point3D:
    return Point3D(x=x, y=0, z=0)


def entity(handle: str) -> EntitySnapshot:
    return EntitySnapshot(
        handle=handle,
        owner_revision="space-r1",
        entity_type="LINE",
        geometry_digest=DIGEST_A,
        layer="0",
    )


def exact_entity(output_id: str) -> ExactEntity:
    return ExactEntity(output_id=output_id, entity_type="LINE", geometry_digest=DIGEST_B, layer="0")


def definition(name: str = "UNIT") -> BlockDefinitionSnapshot:
    return BlockDefinitionSnapshot(
        name=name,
        definition_revision="def-r1",
        base_point=point(),
        members=(entity("A"), entity("B")),
    )


def exact_definition(name: str = "UNIT", member_id: str = "member-1") -> ExactBlockDefinition:
    return ExactBlockDefinition(
        name=name,
        definition_revision="def-r2",
        base_point=point(),
        members=(exact_entity(member_id),),
    )


def reference(handle: str = "10", *, count_key: str = "CHAIR", area_key: str | None = "A") -> BlockReferenceSnapshot:
    return BlockReferenceSnapshot(
        handle=handle,
        reference_revision=f"ref-{handle}",
        block_name="UNIT",
        definition_revision="def-r1",
        insertion_point=point(),
        rotation_radians=0,
        scale_x=1,
        scale_y=1,
        scale_z=1,
        layer="0",
        count_key=count_key,
        area_key=area_key,
    )


def exact_reference(handle: str = "10", scale: float = 2) -> ExactBlockReference:
    return ExactBlockReference(
        source_handle=handle,
        source_revision=f"ref-{handle}",
        result_revision=f"ref-{handle}-after",
        block_name="UNIT",
        insertion_point=point(),
        rotation_radians=0,
        scale_x=scale,
        scale_y=scale,
        scale_z=scale,
        layer="0",
    )


def proposed_reference() -> ProposedBlockReference:
    return ProposedBlockReference(
        output_id="new-ref",
        result_revision="new-ref-r1",
        block_name="UNIT",
        insertion_point=point(),
        rotation_radians=0,
        scale_x=1,
        scale_y=1,
        scale_z=1,
        layer="0",
    )


def test_blx_requires_exact_in_place_replacement() -> None:
    request = MakeBlockInPlaceRequest(
        document_id="D",
        sources=(entity("A"), entity("B")),
        exact_definition=exact_definition(),
        exact_reference=proposed_reference(),
    )
    assert plan_make_block_in_place(request).delete_handles == ("A", "B")
    with pytest.raises(ValueError, match="base point"):
        MakeBlockInPlaceRequest.model_validate(
            request.model_copy(update={"exact_reference": proposed_reference().model_copy(update={"insertion_point": point(9)})}).model_dump()
        )


def test_bqt_recomputes_dcl_rows_from_versioned_references() -> None:
    options = BlockQuantityOptions(
        output=QuantityOutput.CSV_FILE,
        delete_overlapping_before_count=True,
        use_area_groups=True,
        sort_by="name",
        decimal_places=3,
        text_height=2.5,
    )
    request = BlockQuantityRequest(
        document_id="D",
        references=(reference("10"), reference("11"), reference("12", count_key="DESK", area_key="B")),
        options=options,
        excluded_duplicate_handles=("11",),
        exact_rows=(QuantityRow(count_key="CHAIR", area_key="A", quantity=1), QuantityRow(count_key="DESK", area_key="B", quantity=1)),
        exact_output=ExactOutputArtifact(artifact_kind=QuantityOutput.CSV_FILE, target="C:/out/q.csv", content_digest=DIGEST_B),
    )
    assert len(plan_block_quantity(request).rows) == 2
    with pytest.raises(ValueError, match="must equal counts"):
        BlockQuantityRequest.model_validate(
            request.model_copy(update={"exact_rows": (QuantityRow(count_key="CHAIR", area_key="A", quantity=2),)}).model_dump()
        )


def test_brm_requires_proper_member_subset_and_new_revision() -> None:
    request = RemoveBlockMembersRequest(
        document_id="D", definition=definition(), remove_handles=("A",), exact_definition=exact_definition(member_id="B")
    )
    assert plan_remove_block_members(request).remove_handles == ("A",)
    with pytest.raises(ValueError, match="proper subset"):
        RemoveBlockMembersRequest(
            document_id="D", definition=definition(), remove_handles=("A", "B"), exact_definition=exact_definition(member_id="B")
        )


def test_brn_requires_complete_unique_versioned_mapping() -> None:
    request = RenameBlocksRequest(
        document_id="D",
        definitions=(definition(),),
        copy_instead_of_rename=False,
        ignore_existing_name_collisions=False,
        exact_results=(RenameResult(source_name="UNIT", source_revision="def-r1", result_name="UNIT-NEW", result_revision="def-r2"),),
    )
    assert plan_rename_blocks(request).results[0].result_name == "UNIT-NEW"
    with pytest.raises(ValueError, match="must change"):
        RenameBlocksRequest.model_validate(
            request.model_copy(update={"exact_results": (RenameResult(source_name="UNIT", source_revision="def-r1", result_name="UNIT", result_revision="def-r2"),)}).model_dump()
        )


def test_bsc_binds_changed_scale_to_each_source_revision() -> None:
    request = ChangeBlockScaleRequest(document_id="D", references=(reference(),), exact_results=(exact_reference(),))
    assert plan_change_block_scale(request).results[0].scale_x == 2
    with pytest.raises(ValueError, match="change at least one scale"):
        ChangeBlockScaleRequest(
            document_id="D", references=(reference(),), exact_results=(exact_reference(scale=1),)
        )


def test_cx_requires_writable_versioned_file_and_retains_sources() -> None:
    xref = XrefFileSnapshot(xref_name="X", path="C:/x.dwg", file_revision="file-r1", file_sha256=DIGEST_A, writable=True)
    request = CopyObjectsToXrefRequest(
        document_id="D",
        xref=xref,
        sources=(entity("A"),),
        exact_file_entities=(exact_entity("x-a"),),
        exact_file_revision_after="file-r2",
        exact_file_sha256_after=DIGEST_B,
    )
    assert plan_copy_objects_to_xref(request).retain_source_handles == ("A",)
    with pytest.raises(ValueError, match="writable"):
        CopyObjectsToXrefRequest.model_validate(request.model_copy(update={"xref": xref.model_copy(update={"writable": False})}).model_dump())


def test_canonical_approval_and_six_read_only_tools() -> None:
    kwargs = {
        "document_id": "D",
        "references": (reference(),),
        "exact_results": (exact_reference(),),
    }
    draft = ChangeBlockScaleRequest(**kwargs)
    with pytest.raises(ValueError, match="exact approval"):
        ChangeBlockScaleRequest(**kwargs, dry_run=False, approval=Approval(approved=True, fingerprint="sha256:bad"))
    approved = ChangeBlockScaleRequest(
        **kwargs, dry_run=False, approval=Approval(approved=True, fingerprint=draft.fingerprint())
    )
    assert not plan_change_block_scale(approved).dry_run

    mcp = FastMCP("batch28a")
    register_headless_core_batch28a_tools(mcp)
    tools = asyncio.run(mcp.list_tools())
    assert len(tools) == 6
    assert all(tool.annotations and tool.annotations.readOnlyHint for tool in tools)
    assert all(tool.annotations and not tool.annotations.destructiveHint for tool in tools)
