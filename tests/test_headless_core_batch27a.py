import asyncio

import pytest
from mcp.server.fastmcp import FastMCP

from xicad_mcp.headless_core_batch1 import Approval, Point3D
from xicad_mcp.headless_core_batch27a import (
    AddObjectsToBlockRequest,
    AllBlocksExplodeRequest,
    BlockAutoMakeRequest,
    BlockDefinitionSnapshot,
    BlockReferenceSnapshot,
    BlockToXrefRequest,
    EntitySnapshot,
    ExplodedBlockResult,
    LineBetweenBlocksRequest,
    ProposedBlockDefinition,
    ProposedBlockReference,
    ProposedEntity,
    ProposedXref,
    SymbolDrawRequest,
    plan_add_objects_to_block,
    plan_all_blocks_explode,
    plan_block_auto_make,
    plan_block_to_xref,
    plan_line_between_blocks,
    plan_xz_symbol,
    register_headless_core_batch27a_tools,
)


def proposed(name: str) -> ProposedEntity:
    return ProposedEntity(
        output_id=name,
        entity_type="LINE",
        layer="0",
        geometry_payload=(("start", "0,0,0"), ("end", "1,0,0")),
    )


def block(handle: str, x: float = 0) -> BlockReferenceSnapshot:
    return BlockReferenceSnapshot(
        handle=handle,
        block_name=f"B-{handle}",
        definition_revision=f"def-{handle}",
        reference_revision=f"ref-{handle}",
        insertion_point=Point3D(x=x, y=0),
        layer="0",
    )


def entity(handle: str) -> EntitySnapshot:
    return EntitySnapshot(handle=handle, entity_type="LINE", geometry_revision=f"rev-{handle}", layer="0")


def test_xz_requires_unique_explicit_geometry() -> None:
    plan = plan_xz_symbol(
        SymbolDrawRequest(
            document_id="D",
            symbol_kind="caller-reviewed-XZ-variant",
            insertion_point=Point3D(x=10, y=20),
            exact_entities=(proposed("x1"), proposed("x2")),
        )
    )
    assert plan.legacy_symbol == "xiXZ"
    with pytest.raises(ValueError, match="unique"):
        SymbolDrawRequest(
            document_id="D",
            symbol_kind="x",
            insertion_point=Point3D(x=0, y=0),
            exact_entities=(proposed("same"), proposed("same")),
        )


def test_abx_binds_one_exact_result_to_each_versioned_block() -> None:
    plan = plan_all_blocks_explode(
        AllBlocksExplodeRequest(
            document_id="D",
            blocks=(block("A"), block("B")),
            exact_results=(
                ExplodedBlockResult(source_block_handle="A", exact_entities=(proposed("a1"),)),
                ExplodedBlockResult(source_block_handle="B", exact_entities=(proposed("b1"),)),
            ),
        )
    )
    assert plan.delete_handles == ("A", "B")
    with pytest.raises(ValueError, match="one unique"):
        AllBlocksExplodeRequest(
            document_id="D",
            blocks=(block("A"), block("B")),
            exact_results=(ExplodedBlockResult(source_block_handle="A", exact_entities=(proposed("a"),)),),
        )


def test_b2x_versions_target_and_exact_file_output() -> None:
    xref = ProposedXref(
        name="X-A",
        path="C:/exports/a.dwg",
        file_sha256="sha256:" + "a" * 64,
        insertion_point=Point3D(x=0, y=0),
        layer="XREF",
        reference_output_id="xref-1",
    )
    plan = plan_block_to_xref(
        BlockToXrefRequest(
            document_id="D",
            source=block("A"),
            target_path="C:/exports/a.dwg",
            target_revision_before="absent",
            overwrite_existing=False,
            exact_file_entities=(proposed("f1"),),
            exact_xref=xref,
        )
    )
    assert plan.xref.file_sha256.endswith("a" * 64)
    with pytest.raises(ValueError, match="path"):
        BlockToXrefRequest(
            document_id="D",
            source=block("A"),
            target_path="C:/exports/a.dwg",
            target_revision_before="absent",
            overwrite_existing=False,
            exact_file_entities=(proposed("f1"),),
            exact_xref=xref.model_copy(update={"path": "C:/exports/b.dwg"}),
        )


def test_bad_requires_new_definition_revision_and_exact_member_union() -> None:
    definition = BlockDefinitionSnapshot(name="B", definition_revision="r1", member_source_handles=("old",))
    plan = plan_add_objects_to_block(
        AddObjectsToBlockRequest(
            document_id="D",
            definition=definition,
            added_entities=(entity("new"),),
            exact_definition_revision_after="r2",
            exact_member_source_handles_after=("old", "new"),
        )
    )
    assert plan.delete_handles == ("new",)
    with pytest.raises(ValueError, match="old members"):
        AddObjectsToBlockRequest(
            document_id="D",
            definition=definition,
            added_entities=(entity("new"),),
            exact_definition_revision_after="r2",
            exact_member_source_handles_after=("new",),
        )


def test_bam_requires_matching_definition_and_reference() -> None:
    definition = ProposedBlockDefinition(
        name="AUTO-1",
        definition_revision="sha256:def",
        base_point=Point3D(x=0, y=0),
        exact_entities=(proposed("member-1"),),
    )
    plan = plan_block_auto_make(
        BlockAutoMakeRequest(
            document_id="D",
            sources=(entity("A"),),
            exact_definition=definition,
            exact_reference=ProposedBlockReference(
                output_id="ref", block_name="AUTO-1", insertion_point=Point3D(x=0, y=0), layer="0"
            ),
        )
    )
    assert plan.delete_handles == ("A",)
    with pytest.raises(ValueError, match="name"):
        BlockAutoMakeRequest(
            document_id="D",
            sources=(entity("A"),),
            exact_definition=definition,
            exact_reference=ProposedBlockReference(
                output_id="ref", block_name="OTHER", insertion_point=Point3D(x=0, y=0), layer="0"
            ),
        )


def test_bbl_uses_only_explicit_order_and_versioned_insertion_points() -> None:
    plan = plan_line_between_blocks(
        LineBetweenBlocksRequest(
            document_id="D",
            blocks=(block("A", 0), block("B", 10), block("C", 20)),
            ordered_handles=("C", "A", "B"),
            output_layer="LINK",
        )
    )
    assert tuple(point.x for point in plan.vertices) == (20, 0, 10)
    with pytest.raises(ValueError, match="every block"):
        LineBetweenBlocksRequest(
            document_id="D",
            blocks=(block("A"), block("B")),
            ordered_handles=("A", "A"),
            output_layer="LINK",
        )


def test_canonical_approval_and_registration() -> None:
    kwargs = {
        "document_id": "도면-27A",
        "symbol_kind": "exact",
        "insertion_point": Point3D(x=0, y=0),
        "exact_entities": (proposed("x"),),
    }
    draft = SymbolDrawRequest(**kwargs)
    with pytest.raises(ValueError, match="exact approval"):
        SymbolDrawRequest(**kwargs, dry_run=False, approval=Approval(approved=True, fingerprint="sha256:bad"))
    approved = SymbolDrawRequest(
        **kwargs,
        dry_run=False,
        approval=Approval(approved=True, fingerprint=draft.fingerprint()),
    )
    assert approved.fingerprint() == draft.fingerprint()

    mcp = FastMCP("batch27a-test")
    register_headless_core_batch27a_tools(mcp)
    tools = asyncio.run(mcp.list_tools())
    assert len(tools) == 6
    assert all(tool.annotations and tool.annotations.readOnlyHint for tool in tools)
    assert all(tool.annotations and not tool.annotations.destructiveHint for tool in tools)
