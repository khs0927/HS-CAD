from __future__ import annotations

import asyncio

import pytest
from mcp.server.fastmcp import FastMCP

from xicad_mcp.headless_core_batch1 import Approval
from xicad_mcp.headless_core_batch29a import (
    ClippedReferenceSnapshot,
    DefinitionRenameResult,
    ExactEntityResult,
    ExactLayerResult,
    LayoutSnapshot,
    LayoutToModelResult,
    NamedDefinitionSnapshot,
    PaperToModelRequest,
    RemoveBindPrefixRequest,
    ResetXrefLayersRequest,
    VersionedEntity,
    WindowSymbolAction,
    WindowSymbolOptions,
    WindowSymbolRequest,
    WindowSymbolShape,
    XclipExplodeMethod,
    XclipExplodeRequest,
    XclipExplodeResult,
    XrefBindMethod,
    XrefColorOptions,
    XrefColorRequest,
    XrefColorScope,
    XrefLayerSnapshot,
    plan_paper_to_model,
    plan_remove_bind_prefix,
    plan_reset_xref_layers,
    plan_window_symbols,
    plan_xclip_explode,
    plan_xref_color,
    register_headless_core_batch29a_tools,
)

DIGEST_A = "sha256:" + "a" * 64
DIGEST_B = "sha256:" + "b" * 64


def entity(handle: str, *, owner: str = "Model", revision: str = "r1") -> VersionedEntity:
    return VersionedEntity(
        handle=handle,
        revision=revision,
        entity_type="AcDbBlockReference",
        owner=owner,
        state_digest=DIGEST_A,
    )


def exact_entity(result_id: str, *, owner: str = "Model") -> ExactEntityResult:
    return ExactEntityResult(
        result_id=result_id,
        result_revision="r2",
        entity_type="AcDbLine",
        owner=owner,
        state_digest=DIGEST_B,
    )


def layer(name: str = "XREF|A", revision: str = "lr1") -> XrefLayerSnapshot:
    return XrefLayerSnapshot(
        xref_name="XREF",
        layer_name=name,
        revision=revision,
        state_digest=DIGEST_A,
        is_off=False,
        is_frozen=False,
    )


def layer_result(name: str = "XREF|A", revision: str = "lr1") -> ExactLayerResult:
    return ExactLayerResult(
        xref_name="XREF",
        layer_name=name,
        source_revision=revision,
        result_revision="lr2",
        result_digest=DIGEST_B,
    )


def test_rbp_requires_complete_revision_bound_rename_results() -> None:
    source = NamedDefinitionSnapshot(
        symbol_kind="block", name="SITE$0$TREE", revision="d1", definition_digest=DIGEST_A
    )
    result = DefinitionRenameResult(
        symbol_kind="block",
        source_name="SITE$0$TREE",
        source_revision="d1",
        result_name="TREE",
        result_revision="d2",
        result_digest=DIGEST_B,
    )
    request = RemoveBindPrefixRequest(document_id="D", definitions=(source,), exact_results=(result,))
    assert plan_remove_bind_prefix(request).results[0].result_name == "TREE"
    with pytest.raises(ValueError, match="exact source revision"):
        RemoveBindPrefixRequest.model_validate(
            {**request.model_dump(), "exact_results": [{**result.model_dump(), "source_revision": "wrong"}]}
        )


def test_wsl_preserves_current_dcl_modes_and_exact_outputs() -> None:
    options = WindowSymbolOptions(
        action=WindowSymbolAction.LIST,
        shape=WindowSymbolShape.CIRCLE,
        insertion_scale=2.5,
        target_layer="WIN-SYM",
        list_block_gap=1000,
        list_text_height=200,
    )
    request = WindowSymbolRequest(
        document_id="D", sources=(entity("10"),), options=options, exact_results=(exact_entity("20"),)
    )
    assert plan_window_symbols(request).options.action == WindowSymbolAction.LIST
    with pytest.raises(ValueError, match="require versioned"):
        WindowSymbolRequest(document_id="D", sources=(), options=options, exact_results=(exact_entity("20"),))


def test_wsl_user_block_and_change_fields_are_mode_bounded() -> None:
    with pytest.raises(ValueError, match="user block requires"):
        WindowSymbolOptions(
            action=WindowSymbolAction.INSERT,
            shape=WindowSymbolShape.USER_BLOCK,
            insertion_scale=1,
            target_layer="WIN-SYM",
            list_block_gap=100,
            list_text_height=10,
        )
    with pytest.raises(ValueError, match="required only"):
        WindowSymbolOptions(
            action=WindowSymbolAction.LIST,
            shape=WindowSymbolShape.CIRCLE,
            insertion_scale=1,
            target_layer="WIN-SYM",
            list_block_gap=100,
            list_text_height=10,
            change="number",
        )


def test_xcx_binds_recovered_options_to_complete_explicit_results() -> None:
    source = ClippedReferenceSnapshot(
        reference=entity("10"),
        reference_kind="xref",
        clip_boundary_digest=DIGEST_A,
        source_definition_revision="def-r1",
    )
    result = XclipExplodeResult(
        source_handle="10",
        source_revision="r1",
        exact_entities=(exact_entity("20"),),
        source_deleted=True,
    )
    request = XclipExplodeRequest(
        document_id="D",
        references=(source,),
        method=XclipExplodeMethod.CUT_EACH_ENTITY,
        xref_bind_method=XrefBindMethod.BIND,
        exact_results=(result,),
    )
    assert plan_xclip_explode(request).evidence_level.value.startswith("recovered_dcl")
    with pytest.raises(ValueError, match="required exactly"):
        XclipExplodeRequest.model_validate({**request.model_dump(), "xref_bind_method": None})


def test_xrc_filters_versioned_layers_before_accepting_exact_results() -> None:
    options = XrefColorOptions(
        restore=False,
        scope=XrefColorScope.ALL,
        color_index=8,
        include_nested_xrefs=True,
        include_forced_entity_properties=False,
        exclude_off_or_frozen_layers=True,
        excluded_layer_names=("XREF|SKIP",),
    )
    request = XrefColorRequest(
        document_id="D", layers=(layer(),), options=options, exact_results=(layer_result(),)
    )
    assert plan_xref_color(request).options.color_index == 8
    with pytest.raises(ValueError, match="exclude off/frozen"):
        XrefColorRequest.model_validate(
            {**request.model_dump(), "layers": [{**layer().model_dump(), "is_frozen": True}]}
        )


def test_xrr_does_not_invent_opaque_config_reset_state() -> None:
    request = ResetXrefLayersRequest(
        document_id="D", layers=(layer(),), exact_results=(layer_result(),)
    )
    plan = plan_reset_xref_layers(request)
    assert "527 is opaque" in plan.semantic_gaps[0]
    with pytest.raises(ValueError, match="new revisions"):
        ResetXrefLayersRequest.model_validate(
            {
                **request.model_dump(),
                "exact_results": [{**layer_result().model_dump(), "result_revision": "lr1"}],
            }
        )


def test_p2m_requires_one_exact_projection_manifest_per_layout_revision() -> None:
    layout = LayoutSnapshot(
        name="A1",
        revision="layout-r1",
        paper_space_digest=DIGEST_A,
        viewport_digest=DIGEST_A,
        source_entities=(entity("10", owner="A1"),),
    )
    result = LayoutToModelResult(
        layout_name="A1",
        source_revision="layout-r1",
        exact_model_entities=(exact_entity("20"),),
        expected_model_space_revision="model-r2",
        expected_model_space_digest=DIGEST_B,
    )
    request = PaperToModelRequest(
        document_id="D",
        model_space_revision="model-r1",
        model_space_digest=DIGEST_A,
        layouts=(layout,),
        exact_results=(result,),
    )
    assert plan_paper_to_model(request).results[0].expected_model_space_digest == DIGEST_B
    with pytest.raises(ValueError, match="exact layout revision"):
        PaperToModelRequest.model_validate(
            {**request.model_dump(), "exact_results": [{**result.model_dump(), "source_revision": "wrong"}]}
        )


def test_canonical_approval_and_six_read_only_tools() -> None:
    request = ResetXrefLayersRequest(
        document_id="D", layers=(layer(),), exact_results=(layer_result(),)
    )
    with pytest.raises(ValueError, match="exact approval"):
        ResetXrefLayersRequest.model_validate(
            request.model_copy(
                update={"dry_run": False, "approval": Approval(approved=True, fingerprint="sha256:wrong")}
            ).model_dump()
        )
    approved = ResetXrefLayersRequest.model_validate(
        request.model_copy(
            update={
                "dry_run": False,
                "approval": Approval(approved=True, fingerprint=request.fingerprint()),
            }
        ).model_dump()
    )
    assert not plan_reset_xref_layers(approved).dry_run

    mcp = FastMCP("batch29a")
    register_headless_core_batch29a_tools(mcp)
    tools = asyncio.run(mcp.list_tools())
    assert {tool.name for tool in tools} == {
        "xicad_plan_rbp",
        "xicad_plan_wsl",
        "xicad_plan_xcx",
        "xicad_plan_xrc",
        "xicad_plan_xrr",
        "xicad_plan_p2m",
    }
    assert all(tool.annotations and tool.annotations.readOnlyHint for tool in tools)
    assert all(tool.annotations and not tool.annotations.destructiveHint for tool in tools)
