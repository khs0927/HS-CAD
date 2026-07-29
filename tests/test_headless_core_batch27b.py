from __future__ import annotations

import asyncio

import pytest
from mcp.server.fastmcp import FastMCP

from xicad_mcp.headless_core_batch1 import Approval, Point3D
from xicad_mcp.headless_core_batch27b import (
    BlockConditionChangeRequest,
    BlockConditionOptions,
    BlockDefinitionSnapshot,
    BlockEntityState,
    BlockExportResult,
    BlockLayerChangeRequest,
    BlockReferenceSnapshot,
    ChangeBlockRequest,
    CopyBlockDefinitionRequest,
    DefinitionMutationResult,
    EntityAction,
    EntityKind,
    EntityMutationResult,
    ExportBlockRequest,
    ExportFormat,
    ExternalDefinitionSnapshot,
    ExtractedEntityResult,
    RebaseBlockRequest,
    ReferenceReplacementResult,
    ReplacementOptions,
    plan_block_condition_change,
    plan_block_layer_change,
    plan_change_block,
    plan_copy_block_definition,
    plan_export_block,
    plan_rebase_block,
    register_headless_core_batch27b_tools,
)

DIGEST_A = "sha256:" + "a" * 64
DIGEST_B = "sha256:" + "b" * 64


def point(x: float, y: float = 0, z: float = 0) -> Point3D:
    return Point3D(x=x, y=y, z=z)


def entity(path: str = "1", layer: str = "OLD", digest: str = DIGEST_A) -> BlockEntityState:
    return BlockEntityState(
        entity_path=path,
        kind=EntityKind.LINE,
        layer=layer,
        color="ByBlock",
        linetype="Continuous",
        linetype_scale=1,
        geometry_digest=digest,
    )


def definition(name: str = "UNIT", revision: str = "d1", layer: str = "OLD") -> BlockDefinitionSnapshot:
    return BlockDefinitionSnapshot(
        name=name,
        definition_revision=revision,
        base_point=point(0),
        entities=(entity(layer=layer),),
    )


def reference(
    handle: str = "10", revision: str = "r1", block_name: str = "UNIT", layer: str = "REF"
) -> BlockReferenceSnapshot:
    return BlockReferenceSnapshot(
        handle=handle,
        reference_revision=revision,
        block_name=block_name,
        insertion_point=point(10),
        rotation_radians=0.5,
        scale_x=2,
        scale_y=2,
        scale_z=2,
        layer=layer,
    )


def mutation(source: BlockDefinitionSnapshot, target_layer: str = "NEW") -> DefinitionMutationResult:
    changed = entity(layer=target_layer, digest=DIGEST_B)
    return DefinitionMutationResult(
        source_name=source.name,
        source_revision=source.definition_revision,
        result_revision="d2",
        entity_results=(
            EntityMutationResult(source_entity_path="1", action=EntityAction.UPDATE, exact_result=changed),
        ),
    )


def test_bcc_carries_exact_dcl_options_and_one_result_per_versioned_entity() -> None:
    source = definition()
    options = BlockConditionOptions(
        include_dimensions_and_leaders=True,
        target_layer="NEW",
        change_outer_reference_layer=False,
        target_color="7",
        target_linetype="Continuous",
        target_linetype_scale=1,
        explode_nested_blocks=False,
        delete_kinds=frozenset({EntityKind.HATCH}),
        exclude_off_or_frozen_layers=True,
        excluded_layers=("LOCKED",),
        exclude_solids=True,
    )
    request = BlockConditionChangeRequest(
        document_id="D", definitions=(source,), options=options, exact_results=(mutation(source),)
    )
    plan = plan_block_condition_change(request)
    assert plan.options == options
    assert plan.results[0].source_revision == "d1"
    with pytest.raises(ValueError, match="at least 1"):
        BlockConditionChangeRequest.model_validate(
            {**request.model_dump(), "exact_results": [{**mutation(source).model_dump(), "entity_results": []}]}
        )


def test_bch_enforces_dcl_preservation_against_external_definition_snapshot() -> None:
    source = reference()
    replacement = definition(name="NEW_UNIT", revision="ext1")
    exact = reference(handle="20", revision="r2", block_name="NEW_UNIT")
    result = ReferenceReplacementResult(source_handle="10", source_revision="r1", exact_result=exact)
    options = ReplacementOptions(
        preserve_rotation=True, preserve_scale=True, preserve_layer=True, replace_nested_references=False
    )
    request = ChangeBlockRequest(
        document_id="D",
        references=(source,),
        replacement_definition=ExternalDefinitionSnapshot(
            source_uri="C:/blocks/new.dwg", content_digest=DIGEST_A, definition=replacement
        ),
        options=options,
        exact_results=(result,),
    )
    assert plan_change_block(request).replacement_definition.content_digest == DIGEST_A
    with pytest.raises(ValueError, match="preserve_layer"):
        ChangeBlockRequest.model_validate(
            {
                **request.model_dump(),
                "exact_results": [
                    {
                        **result.model_dump(),
                        "exact_result": {**exact.model_dump(), "layer": "WRONG"},
                    }
                ],
            }
        )


def test_bco_requires_existing_unique_entity_paths_and_explicit_destination() -> None:
    source = definition()
    extraction = ExtractedEntityResult(
        source_definition="UNIT",
        source_revision="d1",
        source_entity_path="1",
        destination_owner="ModelSpace",
        exact_result=entity(path="copy:1"),
    )
    request = CopyBlockDefinitionRequest(document_id="D", definitions=(source,), exact_extractions=(extraction,))
    assert plan_copy_block_definition(request).extractions[0].destination_owner == "ModelSpace"
    with pytest.raises(ValueError, match="must exist and be unique"):
        CopyBlockDefinitionRequest.model_validate(
            {**request.model_dump(), "exact_extractions": [{**extraction.model_dump(), "source_entity_path": "404"}]}
        )


def test_bex_binds_unique_file_results_to_definition_revisions_and_hashes() -> None:
    source = definition()
    export = BlockExportResult(
        source_name="UNIT",
        source_revision="d1",
        destination_uri="C:/out/unit.dwg",
        export_format=ExportFormat.DWG,
        overwrite=False,
        expected_content_digest=DIGEST_B,
    )
    request = ExportBlockRequest(document_id="D", definitions=(source,), exact_exports=(export,))
    plan = plan_export_block(request)
    assert plan.exports[0].expected_content_digest == DIGEST_B
    assert not plan.cad_mutation_tool_exposed


def test_bin_requires_exact_rebased_definition_and_one_result_per_reference() -> None:
    source_definition = definition()
    source_reference = reference()
    exact_definition = source_definition.model_copy(update={"definition_revision": "d2", "base_point": point(5)})
    exact_reference = source_reference.model_copy(update={"reference_revision": "r2", "insertion_point": point(20)})
    request = RebaseBlockRequest(
        document_id="D",
        source_definition=source_definition,
        references=(source_reference,),
        new_base_point=point(5),
        exact_definition=exact_definition,
        exact_references=(
            ReferenceReplacementResult(source_handle="10", source_revision="r1", exact_result=exact_reference),
        ),
    )
    assert plan_rebase_block(request).exact_definition.base_point == point(5)
    with pytest.raises(ValueError, match="must differ"):
        RebaseBlockRequest.model_validate(
            {**request.model_dump(), "new_base_point": point(0), "exact_definition": source_definition}
        )


def test_bla_requires_every_entity_to_survive_on_exact_target_layer() -> None:
    source = definition()
    request = BlockLayerChangeRequest(
        document_id="D", definitions=(source,), target_layer="NEW", exact_results=(mutation(source),)
    )
    assert plan_block_layer_change(request).target_layer == "NEW"
    bad = DefinitionMutationResult(
        source_name="UNIT",
        source_revision="d1",
        result_revision="d2",
        entity_results=(EntityMutationResult(source_entity_path="1", action=EntityAction.DELETE, exact_result=None),),
    )
    with pytest.raises(ValueError, match="retain every entity"):
        BlockLayerChangeRequest(document_id="D", definitions=(source,), target_layer="NEW", exact_results=(bad,))


def test_approval_fingerprint_is_canonical_and_exact() -> None:
    source = definition()
    request = BlockLayerChangeRequest(
        document_id="D", definitions=(source,), target_layer="NEW", exact_results=(mutation(source),)
    )
    with pytest.raises(ValueError, match="exact approval"):
        BlockLayerChangeRequest.model_validate(
            request.model_copy(
                update={"dry_run": False, "approval": Approval(approved=True, fingerprint="sha256:wrong")}
            ).model_dump()
        )
    approved = BlockLayerChangeRequest.model_validate(
        request.model_copy(
            update={
                "dry_run": False,
                "approval": Approval(approved=True, fingerprint=request.fingerprint()),
            }
        ).model_dump()
    )
    assert not plan_block_layer_change(approved).dry_run


def test_registers_six_read_only_tools() -> None:
    mcp = FastMCP("batch27b")
    register_headless_core_batch27b_tools(mcp)
    tools = asyncio.run(mcp.list_tools())
    assert {tool.name for tool in tools} == {
        "xicad_plan_bcc",
        "xicad_plan_bch",
        "xicad_plan_bco",
        "xicad_plan_bex",
        "xicad_plan_bin",
        "xicad_plan_bla",
    }
    assert all(tool.annotations and tool.annotations.readOnlyHint for tool in tools)
    assert all(tool.annotations and not tool.annotations.destructiveHint for tool in tools)
