from __future__ import annotations

import asyncio

import pytest
from mcp.server.fastmcp import FastMCP

from xicad_mcp.headless_core_batch1 import Approval, Point3D
from xicad_mcp.headless_core_batch30a import (
    AllViewportUnlockRequest,
    CorrectErrorRequest,
    CorrectionEntitySnapshot,
    CorrectionEntityType,
    CorrectionResult,
    CorrectionScope,
    DrawingBackupRequest,
    EntitySnapshot,
    ExistingDestinationPolicy,
    FileArtifact,
    LayoutFileResult,
    LayoutSnapshot,
    LayoutToDrawingsRequest,
    ViewportResult,
    ViewportRotateRequest,
    ViewportState,
    ViewportUnlockRequest,
    plan_all_viewports_unlock,
    plan_correct_error,
    plan_drawing_backup,
    plan_layout_to_drawings,
    plan_viewport_rotate,
    plan_viewport_unlock,
    register_headless_core_batch30a_tools,
)

DIGEST_A = "sha256:" + "a" * 64
DIGEST_B = "sha256:" + "b" * 64


def entity(handle: str, revision: str = "r1", kind: str = "AcDbViewport") -> EntitySnapshot:
    return EntitySnapshot(handle=handle, revision=revision, entity_type=kind, state_digest=DIGEST_A)


def viewport(handle: str, *, locked: bool = True, twist: float = 0.0) -> ViewportState:
    return ViewportState(
        entity=entity(handle),
        layout_name="Sheet-1",
        layout_revision="layout-r1",
        center=Point3D(x=float(int(handle, 16)), y=20, z=0),
        width=100,
        height=50,
        view_twist_radians=twist,
        display_locked=locked,
    )


def viewport_result(source: ViewportState, *, locked: bool, twist: float | None = None) -> ViewportResult:
    result = source.model_copy(
        update={
            "entity": source.entity.model_copy(update={"revision": "r2", "state_digest": DIGEST_B}),
            "display_locked": locked,
            "view_twist_radians": source.view_twist_radians if twist is None else twist,
        }
    )
    return ViewportResult(
        source_handle=source.entity.handle,
        source_revision=source.entity.revision,
        exact_viewport=result,
        result_manifest_digest=DIGEST_B,
    )


def test_vr_requires_revision_bound_exact_view_twist_result() -> None:
    source = viewport("10", locked=False)
    result = viewport_result(source, locked=False, twist=1.5707963267948966)
    request = ViewportRotateRequest(document_id="D", viewport=source, exact_result=result)
    assert plan_viewport_rotate(request).result.exact_viewport.view_twist_radians == pytest.approx(
        1.5707963267948966
    )
    with pytest.raises(ValueError, match="exact source revision"):
        ViewportRotateRequest.model_validate(
            {
                **request.model_dump(),
                "exact_result": {**result.model_dump(), "source_revision": "old"},
            }
        )


def test_vsd_models_help_page_options_and_content_addressed_outputs() -> None:
    layout = LayoutSnapshot(name="A-101", revision="l1", state_digest=DIGEST_A)
    result = LayoutFileResult(
        source_layout_name="A-101",
        source_layout_revision="l1",
        exact_artifact=FileArtifact(
            path=r"C:\Project\Issue\Project-A-101.dwg", content_digest=DIGEST_B, byte_length=400
        ),
        result_manifest_digest=DIGEST_B,
    )
    request = LayoutToDrawingsRequest(
        document_id="D",
        drawing_revision="d1",
        drawing_digest=DIGEST_A,
        output_folder=r"C:\Project\Issue",
        filename_prefix="Project-",
        prefix_starts_with_drawing_name=False,
        overwrite_same_name=False,
        layouts=(layout,),
        exact_results=(result,),
    )
    assert plan_layout_to_drawings(request).results == (result,)
    with pytest.raises(ValueError, match="containing objects"):
        LayoutToDrawingsRequest.model_validate(
            {**request.model_dump(), "layouts": [{**layout.model_dump(), "contains_objects": False}]}
        )
    with pytest.raises(ValueError, match="unique"):
        LayoutToDrawingsRequest.model_validate(
            {
                **request.model_dump(),
                "layouts": [layout, {**layout.model_dump(), "name": "A-102"}],
                "exact_results": [
                    result,
                    {
                        **result.model_dump(),
                        "source_layout_name": "A-102",
                        "exact_artifact": result.exact_artifact,
                    },
                ],
            }
        )


def test_vu_and_vuu_require_unlocked_complete_scope() -> None:
    sources = (viewport("10"), viewport("20"))
    results = tuple(viewport_result(item, locked=False) for item in sources)
    selected = ViewportUnlockRequest(
        document_id="D", viewports=(sources[0],), exact_results=(results[0],)
    )
    assert plan_viewport_unlock(selected).scope == "selected"
    all_request = AllViewportUnlockRequest(
        document_id="D",
        viewports=sources,
        exact_results=results,
        layout_name="Sheet-1",
        layout_revision="layout-r1",
        complete_viewport_handles=("10", "20"),
    )
    assert plan_all_viewports_unlock(all_request).scope == "all_in_layout_revision"
    with pytest.raises(ValueError, match="complete unique"):
        AllViewportUnlockRequest.model_validate(
            {**all_request.model_dump(), "complete_viewport_handles": ["10"]}
        )
    with pytest.raises(ValueError, match="display_locked false"):
        ViewportUnlockRequest(
            document_id="D",
            viewports=(sources[0],),
            exact_results=(viewport_result(sources[0], locked=True),),
        )


def test_bak_enforces_documented_timestamp_name_and_current_folder() -> None:
    request = DrawingBackupRequest(
        document_id="D",
        source_path=r"C:\Project\Drawing1.dwg",
        source_revision="r7",
        source_digest=DIGEST_A,
        local_timestamp="2026.0722.1540",
        destination_policy=ExistingDestinationPolicy.REQUIRE_ABSENT,
        exact_backup=FileArtifact(
            path=r"C:\Project\Drawing1_2026.0722.1540.dwg",
            content_digest=DIGEST_A,
            byte_length=1200,
        ),
        result_manifest_digest=DIGEST_B,
    )
    assert plan_drawing_backup(request).exact_backup.content_digest == DIGEST_A
    with pytest.raises(ValueError, match="current folder"):
        DrawingBackupRequest.model_validate(
            {
                **request.model_dump(),
                "exact_backup": {
                    **request.exact_backup.model_dump(),
                    "path": r"C:\Other\Drawing1_2026.0722.1540.dwg",
                },
            }
        )
    with pytest.raises(ValueError, match="existing destination digest"):
        DrawingBackupRequest.model_validate(
            {
                **request.model_dump(),
                "destination_policy": "require_matching_digest",
            }
        )


def test_cer_preserves_dcl_filters_and_requires_complete_explicit_results() -> None:
    source = CorrectionEntitySnapshot(
        handle="30", revision="r1", entity_type=CorrectionEntityType.LINE, state_digest=DIGEST_A
    )
    corrected = EntitySnapshot(
        handle="30", revision="r2", entity_type="AcDbLine", state_digest=DIGEST_B
    )
    result = CorrectionResult(
        source_handle="30",
        source_revision="r1",
        exact_entity=corrected,
        result_manifest_digest=DIGEST_B,
    )
    request = CorrectErrorRequest(
        document_id="D",
        selection_scope=CorrectionScope.SCREEN_SELECTION,
        reference_point=Point3D(x=0, y=0, z=0),
        exact_corrected_reference_point=Point3D(x=0, y=0, z=0),
        enabled_entity_types=frozenset({CorrectionEntityType.LINE}),
        tolerance=0.1,
        correct_circle_arc_radius=False,
        entities=(source,),
        exact_results=(result,),
    )
    plan = plan_correct_error(request)
    assert plan.tolerance == pytest.approx(0.1)
    assert plan.evidence_level.value == "dcl_inputs_explicit_result_not_legacy_equivalent"
    with pytest.raises(ValueError, match="enabled"):
        CorrectErrorRequest.model_validate(
            {
                **request.model_dump(),
                "entities": [{**source.model_dump(), "entity_type": "CIRCLE"}],
            }
        )


def test_approval_and_six_read_only_tool_annotations() -> None:
    source = viewport("10")
    request = ViewportUnlockRequest(
        document_id="D", viewports=(source,), exact_results=(viewport_result(source, locked=False),)
    )
    with pytest.raises(ValueError, match="exact approval"):
        ViewportUnlockRequest.model_validate(
            request.model_copy(
                update={"dry_run": False, "approval": Approval(approved=True, fingerprint="sha256:wrong")}
            ).model_dump()
        )
    approved = ViewportUnlockRequest.model_validate(
        request.model_copy(
            update={
                "dry_run": False,
                "approval": Approval(approved=True, fingerprint=request.fingerprint()),
            }
        ).model_dump()
    )
    assert not plan_viewport_unlock(approved).dry_run

    mcp = FastMCP("batch30a")
    register_headless_core_batch30a_tools(mcp)
    tools = asyncio.run(mcp.list_tools())
    assert {tool.name for tool in tools} == {
        "xicad_plan_vr",
        "xicad_plan_vsd",
        "xicad_plan_vu",
        "xicad_plan_vuu",
        "xicad_plan_bak",
        "xicad_plan_cer",
    }
    assert all(tool.annotations and tool.annotations.readOnlyHint for tool in tools)
    assert all(tool.annotations and not tool.annotations.destructiveHint for tool in tools)
