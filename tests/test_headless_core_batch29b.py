from __future__ import annotations

import asyncio

import pytest
from mcp.server.fastmcp import FastMCP

from xicad_mcp.headless_core_batch1 import Approval, Point3D
from xicad_mcp.headless_core_batch29b import (
    AllViewportLockRequest,
    EntitySnapshot,
    GeneratedEntityResult,
    ModelGeometrySnapshot,
    ViewportAlignRequest,
    ViewportCreationResult,
    ViewportGuideLineRequest,
    ViewportLayerPropertyRequest,
    ViewportLayerResult,
    ViewportLayerSnapshot,
    ViewportLockRequest,
    ViewportMakeObjectRequest,
    ViewportResult,
    ViewportSnapshot,
    plan_all_viewports_lock,
    plan_viewport_align,
    plan_viewport_guide_line,
    plan_viewport_layer_property,
    plan_viewport_lock,
    plan_viewport_make_object,
    register_headless_core_batch29b_tools,
)

DIGEST_A = "sha256:" + "a" * 64
DIGEST_B = "sha256:" + "b" * 64


def entity(handle: str, revision: str = "r1", kind: str = "AcDbViewport") -> EntitySnapshot:
    return EntitySnapshot(handle=handle, revision=revision, entity_type=kind, state_digest=DIGEST_A)


def viewport(handle: str, *, revision: str = "r1", locked: bool = False) -> ViewportSnapshot:
    return ViewportSnapshot(
        entity=entity(handle, revision),
        layout_name="Sheet-1",
        layout_revision="layout-r1",
        center=Point3D(x=float(int(handle, 16)), y=20, z=0),
        width=100,
        height=50,
        display_locked=locked,
    )


def viewport_result(source: ViewportSnapshot, *, locked: bool | None = None) -> ViewportResult:
    result = source.model_copy(
        update={
            "entity": source.entity.model_copy(update={"revision": "r2", "state_digest": DIGEST_B}),
            "display_locked": source.display_locked if locked is None else locked,
        }
    )
    return ViewportResult(
        source_handle=source.entity.handle,
        source_revision=source.entity.revision,
        exact_viewport=result,
        result_manifest_digest=DIGEST_B,
    )


def test_va_requires_complete_revision_bound_results() -> None:
    sources = (viewport("10"), viewport("20"))
    request = ViewportAlignRequest(
        document_id="D", viewports=sources, exact_results=tuple(viewport_result(item) for item in sources)
    )
    assert len(plan_viewport_align(request).results) == 2
    with pytest.raises(ValueError, match="exact source revision"):
        ViewportAlignRequest.model_validate(
            {
                **request.model_dump(),
                "exact_results": [
                    {**request.exact_results[0].model_dump(), "source_revision": "wrong"},
                    request.exact_results[1],
                ],
            }
        )


def test_vgl_binds_explicit_geometry_to_viewport_revision() -> None:
    source = viewport("10")
    result = GeneratedEntityResult(
        source_handle="10",
        source_revision="r1",
        exact_entities=(entity("30", "r2", "AcDbPolyline"),),
        result_manifest_digest=DIGEST_B,
    )
    request = ViewportGuideLineRequest(document_id="D", viewports=(source,), exact_results=(result,))
    assert plan_viewport_guide_line(request).results == (result,)
    with pytest.raises(ValueError, match="exact viewport revision"):
        ViewportGuideLineRequest.model_validate(
            {**request.model_dump(), "exact_results": [{**result.model_dump(), "source_revision": "old"}]}
        )


def test_vl_and_vll_require_locked_complete_scope() -> None:
    sources = (viewport("10"), viewport("20"))
    results = tuple(viewport_result(item, locked=True) for item in sources)
    selected = ViewportLockRequest(document_id="D", viewports=(sources[0],), exact_results=(results[0],))
    assert plan_viewport_lock(selected).scope == "selected"
    all_request = AllViewportLockRequest(
        document_id="D",
        viewports=sources,
        exact_results=results,
        layout_name="Sheet-1",
        layout_revision="layout-r1",
        complete_viewport_handles=("10", "20"),
    )
    assert plan_all_viewports_lock(all_request).scope == "all_in_layout_revision"
    with pytest.raises(ValueError, match="complete unique"):
        AllViewportLockRequest.model_validate(
            {**all_request.model_dump(), "complete_viewport_handles": ["10"]}
        )
    with pytest.raises(ValueError, match="display_locked true"):
        ViewportLockRequest(
            document_id="D", viewports=(sources[0],), exact_results=(viewport_result(sources[0]),)
        )


def test_vmo_requires_closed_sources_and_exact_target_layout() -> None:
    source = ModelGeometrySnapshot(entity=entity("40", kind="AcDbPolyline"), closed_boundary=True)
    result = ViewportCreationResult(
        source_handle="40",
        source_revision="r1",
        exact_viewport=viewport("50", revision="r2"),
        result_manifest_digest=DIGEST_B,
    )
    request = ViewportMakeObjectRequest(
        document_id="D",
        target_layout_name="Sheet-1",
        target_layout_revision="layout-r1",
        model_geometry=(source,),
        exact_results=(result,),
    )
    assert plan_viewport_make_object(request).results == (result,)
    with pytest.raises(ValueError, match="closed boundaries"):
        ViewportMakeObjectRequest.model_validate(
            {
                **request.model_dump(),
                "model_geometry": [{**source.model_dump(), "closed_boundary": False}],
            }
        )


def test_vpp_binds_opaque_override_results_to_both_revisions() -> None:
    source = ViewportLayerSnapshot(
        viewport_handle="10",
        viewport_revision="v1",
        layer_name="WALL",
        layer_revision="l1",
        override_state_digest=DIGEST_A,
    )
    result = ViewportLayerResult(
        viewport_handle="10",
        viewport_revision="v1",
        layer_name="WALL",
        layer_revision="l1",
        exact_override_state_digest=DIGEST_B,
        result_manifest_digest=DIGEST_B,
    )
    request = ViewportLayerPropertyRequest(document_id="D", states=(source,), exact_results=(result,))
    assert plan_viewport_layer_property(request).results == (result,)
    with pytest.raises(ValueError, match="exact viewport and layer revisions"):
        ViewportLayerPropertyRequest.model_validate(
            {**request.model_dump(), "exact_results": [{**result.model_dump(), "layer_revision": "old"}]}
        )


def test_approval_and_six_read_only_tool_annotations() -> None:
    source = viewport("10")
    request = ViewportLockRequest(
        document_id="D", viewports=(source,), exact_results=(viewport_result(source, locked=True),)
    )
    with pytest.raises(ValueError, match="exact approval"):
        ViewportLockRequest.model_validate(
            request.model_copy(
                update={"dry_run": False, "approval": Approval(approved=True, fingerprint="sha256:wrong")}
            ).model_dump()
        )
    approved = ViewportLockRequest.model_validate(
        request.model_copy(
            update={
                "dry_run": False,
                "approval": Approval(approved=True, fingerprint=request.fingerprint()),
            }
        ).model_dump()
    )
    assert not plan_viewport_lock(approved).dry_run

    mcp = FastMCP("batch29b")
    register_headless_core_batch29b_tools(mcp)
    tools = asyncio.run(mcp.list_tools())
    assert {tool.name for tool in tools} == {
        "xicad_plan_va",
        "xicad_plan_vgl",
        "xicad_plan_vl",
        "xicad_plan_vll",
        "xicad_plan_vmo",
        "xicad_plan_vpp",
    }
    assert all(tool.annotations and tool.annotations.readOnlyHint for tool in tools)
    assert all(tool.annotations and not tool.annotations.destructiveHint for tool in tools)
