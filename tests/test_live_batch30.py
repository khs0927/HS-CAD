from __future__ import annotations

import asyncio
from typing import Any

import pytest
from mcp.server.fastmcp import FastMCP

from xicad_mcp import live_batch30 as live
from xicad_mcp.headless_core_batch1 import Point3D
from xicad_mcp.headless_core_batch30a import (
    AllViewportUnlockRequest,
    EntitySnapshot,
    ViewportResult,
    ViewportState,
    ViewportUnlockRequest,
)
from xicad_mcp.headless_core_batch30b import (
    DeletedEntityResult,
    DeletePlotBoxesRequest,
    VersionedEntitySnapshot,
)

DIGEST_A = "sha256:" + "a" * 64
DIGEST_B = "sha256:" + "b" * 64


class Layer:
    def __init__(self, name: str, locked: bool = False) -> None:
        self.Name, self.Lock = name, locked


class Layers:
    def __init__(self) -> None:
        self.items = {
            "VIEWPORTS": Layer("VIEWPORTS"),
            "PLOT_BOX": Layer("PLOT_BOX"),
        }

    def Item(self, name: str) -> Layer:
        return self.items[name]


class Viewport:
    ObjectName = "AcDbViewport"

    def __init__(self, handle: str, center: tuple[float, float, float], number: int = 2) -> None:
        self.Handle, self.Layer, self.Center = handle, "VIEWPORTS", center
        self.Width, self.Height, self.TwistAngle = 100.0, 80.0, 0.25
        self.DisplayLocked, self.Number = True, number


class PlotBox:
    ObjectName = "AcDbPolyline"

    def __init__(self, handle: str, doc: Doc) -> None:
        self.Handle, self.Layer, self.doc = handle, "PLOT_BOX", doc

    def Delete(self) -> None:
        self.doc.entities = [item for item in self.doc.entities if item is not self]


class Doc:
    Name = "Drawing1.dwg"

    def __init__(self) -> None:
        self.Layers = Layers()
        self.entities: list[Any] = [
            Viewport("PAPER", (0.0, 0.0, 0.0), 1),
            Viewport("V1", (50.0, 40.0, 0.0)),
            Viewport("V2", (180.0, 40.0, 0.0), 3),
        ]
        self.marks: list[str] = []

    def StartUndoMark(self) -> None:
        self.marks.append("start")

    def EndUndoMark(self) -> None:
        self.marks.append("end")


@pytest.fixture
def doc(monkeypatch: pytest.MonkeyPatch) -> Doc:
    drawing = Doc()
    monkeypatch.setattr(live, "_drawing", lambda _name: drawing)

    def entities(_doc: Doc) -> dict[str, tuple[Any, str]]:
        return {item.Handle.casefold(): (item, "Sheet-1" if isinstance(item, Viewport) else "Model") for item in drawing.entities}

    monkeypatch.setattr(live, "_entities", entities)
    return drawing


def viewport_snapshot(item: Viewport) -> ViewportState:
    return ViewportState(
        entity=EntitySnapshot(
            handle=item.Handle,
            revision=f"source-{item.Handle}",
            entity_type=item.ObjectName,
            state_digest=DIGEST_A,
        ),
        layout_name="Sheet-1",
        layout_revision="layout-1",
        center=Point3D(x=item.Center[0], y=item.Center[1], z=item.Center[2]),
        width=item.Width,
        height=item.Height,
        view_twist_radians=item.TwistAngle,
        display_locked=item.DisplayLocked,
        is_paper_viewport=item.Number == 1,
    )


def viewport_result(source: ViewportState) -> ViewportResult:
    target = source.model_copy(
        update={
            "entity": source.entity.model_copy(update={"revision": "result", "state_digest": DIGEST_B}),
            "display_locked": False,
        }
    )
    return ViewportResult(
        source_handle=source.entity.handle,
        source_revision=source.entity.revision,
        exact_viewport=target,
        result_manifest_digest=DIGEST_B,
    )


def test_vu_preview_execute_stale_and_postcondition(doc: Doc) -> None:
    source = viewport_snapshot(doc.entities[1])
    request = ViewportUnlockRequest(
        document_id=doc.Name,
        viewports=(source,),
        exact_results=(viewport_result(source),),
    )
    preview = live.preview_live_vu(request)
    assert preview["live_executable"] and preview["mutation"]
    execute = live.LiveVUExecuteRequest(
        request=request,
        expected_sources=tuple(live.LiveViewportEvidence.model_validate(item) for item in preview["expected_sources"]),
        approval_fingerprint=preview["approval_fingerprint"],
    )
    result = live.execute_live_vu(execute)
    assert result.changed_handles == ("V1",)
    assert result.postcondition_verified and doc.marks == ["start", "end"]
    assert not doc.entities[1].DisplayLocked

    doc.entities[1].DisplayLocked = True
    stale = execute.model_copy(
        update={"expected_sources": (execute.expected_sources[0].model_copy(update={"width": 99.0}),)}
    )
    with pytest.raises(ValueError, match="approval fingerprint"):
        live.execute_live_vu(stale)


def test_vuu_requires_complete_live_layout_scope(doc: Doc) -> None:
    sources = tuple(viewport_snapshot(item) for item in doc.entities[1:3])
    request = AllViewportUnlockRequest(
        document_id=doc.Name,
        viewports=sources,
        exact_results=tuple(viewport_result(item) for item in sources),
        layout_name="Sheet-1",
        layout_revision="layout-1",
        complete_viewport_handles=("V1", "V2"),
    )
    preview = live.preview_live_vuu(request)
    result = live.execute_live_vuu(
        live.LiveVUUExecuteRequest(
            request=request,
            expected_sources=tuple(live.LiveViewportEvidence.model_validate(item) for item in preview["expected_sources"]),
            approval_fingerprint=preview["approval_fingerprint"],
        )
    )
    assert result.changed_handles == ("V1", "V2")
    assert all(not item.DisplayLocked for item in doc.entities[1:3])

    for item in doc.entities[1:3]:
        item.DisplayLocked = True
    narrowed = request.model_copy(update={"complete_viewport_handles": ("V1",)})
    with pytest.raises(ValueError, match="complete live layout"):
        live.preview_live_vuu(narrowed)


def pbd_request(doc: Doc) -> DeletePlotBoxesRequest:
    boxes = tuple(
        VersionedEntitySnapshot(
            handle=item.Handle,
            revision=f"source-{item.Handle}",
            entity_type=item.ObjectName,
            owner="Model",
            layer=item.Layer,
            state_digest=DIGEST_A,
        )
        for item in doc.entities
        if isinstance(item, PlotBox)
    )
    return DeletePlotBoxesRequest(
        document_id=doc.Name,
        owner="Model",
        owner_revision="model-1",
        complete_plot_box_handles=tuple(item.handle for item in boxes),
        plot_boxes=boxes,
        exact_results=tuple(
            DeletedEntityResult(source_handle=item.handle, source_revision=item.revision, deleted=True)
            for item in boxes
        ),
    )


def test_pbd_deletes_only_complete_plot_box_scope_with_undo(doc: Doc) -> None:
    doc.entities.extend((PlotBox("B1", doc), PlotBox("B2", doc)))
    request = pbd_request(doc)
    preview = live.preview_live_pbd(request)
    assert preview["official_help_url"] == "https://izzarder.com/43"
    result = live.execute_live_pbd(
        live.LivePBDExecuteRequest(
            request=request,
            expected_sources=tuple(live.LivePlotBoxEvidence.model_validate(item) for item in preview["expected_sources"]),
            approval_fingerprint=preview["approval_fingerprint"],
        )
    )
    assert result.changed_handles == ("B1", "B2")
    assert not any(isinstance(item, PlotBox) for item in doc.entities)
    assert doc.marks == ["start", "end"]


def test_locked_layer_and_incomplete_pbd_scope_are_rejected(doc: Doc) -> None:
    doc.entities.extend((PlotBox("B1", doc), PlotBox("B2", doc)))
    request = pbd_request(doc)
    incomplete = request.model_copy(
        update={
            "complete_plot_box_handles": ("B1",),
            "plot_boxes": (request.plot_boxes[0],),
            "exact_results": (request.exact_results[0],),
        }
    )
    with pytest.raises(ValueError, match="complete live owner"):
        live.preview_live_pbd(incomplete)
    doc.Layers.items["PLOT_BOX"].Lock = True
    with pytest.raises(ValueError, match="locked or xref"):
        live.preview_live_pbd(request)


def test_registers_twelve_previews_and_three_destructive_execute_tools() -> None:
    mcp = FastMCP("batch30-live")
    live.register_live_batch30_tools(mcp)
    tools = asyncio.run(mcp.list_tools())
    assert len(tools) == 15
    assert {tool.name for tool in tools if tool.name.startswith("xicad_execute_live_")} == {
        "xicad_execute_live_vu",
        "xicad_execute_live_vuu",
        "xicad_execute_live_pbd",
    }
    writes = [tool for tool in tools if tool.name.startswith("xicad_execute_live_")]
    assert all(tool.annotations and tool.annotations.destructiveHint for tool in writes)
    assert all(tool.annotations and not tool.annotations.readOnlyHint for tool in writes)
