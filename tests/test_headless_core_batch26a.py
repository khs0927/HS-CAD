import asyncio

import pytest
from mcp.server.fastmcp import FastMCP

from xicad_mcp.headless_core_batch1 import Approval, Point3D
from xicad_mcp.headless_core_batch26a import (
    PolylineJoinRequest,
    PolylineSnapshot,
    PolylineVertex,
    PolylineWidthRequest,
    ProposedPolylineResult,
    ProposedVertexTableRow,
    VertexAddRequest,
    VertexDeleteRequest,
    VertexListTableRequest,
    VertexRemoveCleanRequest,
    plan_polyline_join,
    plan_polyline_width,
    plan_vertex_add,
    plan_vertex_delete,
    plan_vertex_list_table,
    plan_vertex_remove_clean,
    register_headless_core_batch26a_tools,
)


def vertex(name: str, x: float, width: float = 0) -> PolylineVertex:
    return PolylineVertex(
        vertex_id=name,
        point=Point3D(x=x, y=0),
        start_width=width,
        end_width=width,
    )


def snapshot(handle: str, vertices: tuple[PolylineVertex, ...]) -> PolylineSnapshot:
    return PolylineSnapshot(
        handle=handle,
        entity_type="LWPOLYLINE",
        geometry_revision=f"rev-{handle}",
        layer="WALL",
        closed=False,
        vertices=vertices,
    )


def result(
    result_id: str,
    sources: tuple[str, ...],
    vertices: tuple[PolylineVertex, ...],
) -> ProposedPolylineResult:
    return ProposedPolylineResult(
        result_id=result_id,
        source_handles=sources,
        entity_type="LWPOLYLINE",
        layer="WALL",
        closed=False,
        vertices=vertices,
    )


def test_pj_requires_all_versioned_sources_and_exact_result() -> None:
    a = snapshot("A", (vertex("a0", 0), vertex("a1", 1)))
    b = snapshot("B", (vertex("b0", 1), vertex("b1", 2)))
    exact = result("joined", ("A", "B"), (*a.vertices, *b.vertices))
    plan = plan_polyline_join(
        PolylineJoinRequest(
            document_id="D",
            sources=(a, b),
            exact_result=exact,
            delete_source_handles=("A", "B"),
        )
    )
    assert plan.legacy_symbol == "xiPolylineJoin"
    assert plan.exact_result == exact
    with pytest.raises(ValueError, match="every source"):
        PolylineJoinRequest(
            document_id="D",
            sources=(a, b),
            exact_result=result("bad", ("A",), a.vertices),
            delete_source_handles=("A", "B"),
        )


def test_pv_requires_exactly_one_added_vertex_and_retains_order() -> None:
    source = snapshot("A", (vertex("v0", 0), vertex("v1", 2)))
    exact = result("A2", ("A",), (vertex("v0", 0), vertex("new", 1), vertex("v1", 2)))
    plan = plan_vertex_add(
        VertexAddRequest(document_id="D", source=source, exact_result=exact)
    )
    assert plan.command_alias == "PV"
    with pytest.raises(ValueError, match="add exactly one"):
        VertexAddRequest(
            document_id="D",
            source=source,
            exact_result=result("bad", ("A",), (vertex("v1", 2), vertex("new", 1), vertex("v0", 0))),
        )


def test_pvr_and_pvv_preserve_retained_vertex_order() -> None:
    source = snapshot("A", tuple(vertex(f"v{i}", i) for i in range(5)))
    clean = result("clean", ("A",), (source.vertices[0], source.vertices[2], source.vertices[4]))
    clean_plan = plan_vertex_remove_clean(
        VertexRemoveCleanRequest(document_id="D", source=source, exact_result=clean)
    )
    assert clean_plan.command_alias == "PVR"
    deleted = result("deleted", ("A",), source.vertices[:-1])
    delete_plan = plan_vertex_delete(
        VertexDeleteRequest(document_id="D", source=source, exact_result=deleted)
    )
    assert delete_plan.command_alias == "PVV"
    with pytest.raises(ValueError, match="exactly one"):
        VertexDeleteRequest(document_id="D", source=source, exact_result=clean)


def test_pvl_requires_one_explicit_row_per_versioned_vertex() -> None:
    source = snapshot("A", (vertex("v0", 0), vertex("v1", 2)))
    rows = (
        ProposedVertexTableRow(source_handle="A", vertex_id="v0", cells=("1", "0.0")),
        ProposedVertexTableRow(source_handle="A", vertex_id="v1", cells=("2", "2.0")),
    )
    plan = plan_vertex_list_table(
        VertexListTableRequest(
            document_id="D",
            sources=(source,),
            columns=("NO", "X"),
            exact_rows=rows,
            insertion_point=Point3D(x=10, y=20),
            output_layer="TABLE",
            text_height=250,
        )
    )
    assert plan.exact_rows == rows
    assert "caller supplied" in plan.semantic_gaps[2]


def test_pw_allows_width_only_and_rejects_topology_change() -> None:
    source = snapshot("A", (vertex("v0", 0), vertex("v1", 2)))
    widened = result("wide", ("A",), (vertex("v0", 0, 100), vertex("v1", 2, 200)))
    plan = plan_polyline_width(
        PolylineWidthRequest(document_id="D", source=source, exact_result=widened)
    )
    assert plan.exact_result.vertices[1].start_width == 200
    moved = result("moved", ("A",), (vertex("v0", 0, 100), vertex("v1", 3, 200)))
    with pytest.raises(ValueError, match="only per-vertex"):
        PolylineWidthRequest(document_id="D", source=source, exact_result=moved)


def test_non_dry_run_requires_canonical_approval() -> None:
    source = snapshot("A", (vertex("v0", 0), vertex("v1", 2)))
    widened = result("wide", ("A",), (vertex("v0", 0, 100), vertex("v1", 2, 100)))
    draft = PolylineWidthRequest(document_id="도면", source=source, exact_result=widened)
    with pytest.raises(ValueError, match="exact approval fingerprint"):
        PolylineWidthRequest(
            document_id="도면",
            source=source,
            exact_result=widened,
            dry_run=False,
            approval=Approval(approved=True, fingerprint="sha256:wrong"),
        )
    approved = PolylineWidthRequest(
        document_id="도면",
        source=source,
        exact_result=widened,
        dry_run=False,
        approval=Approval(approved=True, fingerprint=draft.fingerprint()),
    )
    assert approved.fingerprint() == draft.fingerprint()


def test_registers_six_read_only_tools() -> None:
    mcp = FastMCP("batch26a-test")
    register_headless_core_batch26a_tools(mcp)
    tools = asyncio.run(mcp.list_tools())
    assert len(tools) == 6
    assert all(tool.annotations and tool.annotations.readOnlyHint for tool in tools)
    assert all(tool.annotations and not tool.annotations.destructiveHint for tool in tools)
