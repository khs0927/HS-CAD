import asyncio

import pytest
from mcp.server.fastmcp import FastMCP

from xicad_mcp.headless_core_batch1 import Point3D
from xicad_mcp.headless_core_batch20a import (
    CurveKind,
    CurveSnapshot,
    CutAlias,
    CutRequest,
    EditRole,
    IntersectionEvidence,
    ProposedCurveEdit,
    plan_cut,
    register_headless_core_batch20a_tools,
)


def curve(handle: str) -> CurveSnapshot:
    return CurveSnapshot(handle=handle, kind=CurveKind.LINE, vertices=(Point3D(x=0, y=0), Point3D(x=1, y=1)), layer="W")


def intersection(*handles: str) -> IntersectionEvidence:
    return IntersectionEvidence(point=Point3D(x=0.5, y=0.5), participating_handles=handles)


def edit(handle: str, role: EditRole = EditRole.TRIM) -> ProposedCurveEdit:
    parts = ((Point3D(x=0, y=0), Point3D(x=0.5, y=0.5)),)
    if role is EditRole.BREAK:
        parts = parts + ((Point3D(x=0.5, y=0.5), Point3D(x=1, y=1)),)
    return ProposedCurveEdit(source_handle=handle, role=role, output_parts=parts)


def request(alias: CutAlias, handles: tuple[str, ...], edits: tuple[ProposedCurveEdit, ...], **kwargs) -> CutRequest:
    return CutRequest(
        document_id="D",
        alias=alias,
        source_handles=handles,
        intersections=(intersection(*handles),),
        proposed_edits=edits,
        topology_tolerance=0.001,
        delete_originals=True,
        **kwargs,
    )


def test_fe_requires_retained_length_and_echoes_validated_geometry() -> None:
    with pytest.raises(ValueError, match="retained_length"):
        request(CutAlias.FE, ("A", "B"), (edit("A"), edit("B")))
    plan = plan_cut(
        request(CutAlias.FE, ("A", "B"), (edit("A"), edit("B")), retained_length=10), (curve("A"), curve("B"))
    )
    assert plan.legacy_symbol == "xiFilletExtend" and plan.retained_length == 10


def test_fm_accepts_explicit_multi_corner_result_only() -> None:
    plan = plan_cut(
        request(CutAlias.FM, ("A", "B", "C"), (edit("A"), edit("B"), edit("C"))), (curve("A"), curve("B"), curve("C"))
    )
    assert len(plan.validated_sources) == 3


def test_fr_requires_radius_but_does_not_invent_arc_side() -> None:
    with pytest.raises(ValueError, match="wall_radius"):
        request(CutAlias.FR, ("A", "B"), (edit("A"), edit("B")))
    plan = plan_cut(request(CutAlias.FR, ("A", "B"), (edit("A"), edit("B")), wall_radius=100), (curve("A"), curve("B")))
    assert "intersection choice" in plan.semantic_gaps


@pytest.mark.parametrize(("alias", "count"), ((CutAlias.FT, 3), (CutAlias.FX, 4)))
def test_wall_topology_commands_require_exact_source_count(alias: CutAlias, count: int) -> None:
    handles = tuple(chr(65 + index) for index in range(count))
    plan = plan_cut(
        request(alias, handles, tuple(edit(handle) for handle in handles)), tuple(curve(handle) for handle in handles)
    )
    assert len(plan.validated_sources) == count
    with pytest.raises(ValueError, match="requires exactly"):
        request(alias, handles[:-1], tuple(edit(handle) for handle in handles[:-1]))


def test_xt_requires_both_break_and_extend_roles() -> None:
    with pytest.raises(ValueError, match="break and extend"):
        request(CutAlias.XT, ("A", "B"), (edit("A", EditRole.BREAK),))
    plan = plan_cut(
        request(CutAlias.XT, ("A", "B"), (edit("A", EditRole.BREAK), edit("B", EditRole.EXTEND))),
        (curve("A"), curve("B")),
    )
    assert {item.role for item in plan.proposed_edits} == {EditRole.BREAK, EditRole.EXTEND}


def test_non_dry_requires_approval_fingerprint() -> None:
    with pytest.raises(ValueError, match="approval fingerprint"):
        CutRequest(
            document_id="D",
            alias=CutAlias.FE,
            source_handles=("A", "B"),
            intersections=(intersection("A", "B"),),
            proposed_edits=(edit("A"), edit("B")),
            retained_length=1,
            topology_tolerance=0.001,
            delete_originals=True,
            dry_run=False,
        )


def test_registers_six_read_only_tools() -> None:
    mcp = FastMCP("batch20a-test")
    register_headless_core_batch20a_tools(mcp)
    tools = asyncio.run(mcp.list_tools())
    assert len(tools) == 6
    assert all(tool.annotations and tool.annotations.readOnlyHint for tool in tools)
