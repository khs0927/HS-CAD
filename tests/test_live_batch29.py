from __future__ import annotations

from typing import Any

import pytest

from xicad_mcp import live_batch29 as live
from xicad_mcp.headless_core_batch1 import Point3D
from xicad_mcp.headless_core_batch29b import (
    AllViewportLockRequest,
    EntitySnapshot,
    ViewportLockRequest,
    ViewportResult,
    ViewportSnapshot,
)

DIGEST_A = "sha256:" + "a" * 64
DIGEST_B = "sha256:" + "b" * 64


class Layer:
    def __init__(self, name: str, locked: bool = False) -> None:
        self.Name, self.Lock = name, locked


class Layers:
    def __init__(self) -> None:
        self.items = {"VIEWPORTS": Layer("VIEWPORTS")}

    def Item(self, name: str) -> Layer:
        return self.items[name]


class Viewport:
    ObjectName = "AcDbViewport"

    def __init__(self, handle: str, center: tuple[float, float, float], number: int = 2) -> None:
        self.Handle, self.Layer, self.Center = handle, "VIEWPORTS", center
        self.Width, self.Height = 100.0, 80.0
        self.DisplayLocked, self.Number = False, number


class Doc:
    Name = "Drawing1.dwg"

    def __init__(self) -> None:
        self.Layers = Layers()
        self.entities = [
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
    monkeypatch.setattr(
        live,
        "_entities",
        lambda _doc: {item.Handle.casefold(): (item, "Layout1") for item in drawing.entities},
    )
    return drawing


def snapshot(item: Viewport) -> ViewportSnapshot:
    return ViewportSnapshot(
        entity=EntitySnapshot(
            handle=item.Handle,
            revision=f"source-{item.Handle}",
            entity_type=item.ObjectName,
            state_digest=DIGEST_A,
        ),
        layout_name="Layout1",
        layout_revision="layout-1",
        center=Point3D(x=item.Center[0], y=item.Center[1], z=item.Center[2]),
        width=item.Width,
        height=item.Height,
        display_locked=item.DisplayLocked,
        is_paper_viewport=item.Number == 1,
    )


def result(source: ViewportSnapshot) -> ViewportResult:
    target_entity = source.entity.model_copy(update={"revision": f"result-{source.entity.handle}", "state_digest": DIGEST_B})
    target = source.model_copy(update={"entity": target_entity, "display_locked": True})
    return ViewportResult(
        source_handle=source.entity.handle,
        source_revision=source.entity.revision,
        exact_viewport=target,
        result_manifest_digest=DIGEST_B,
    )


def selected_request(doc: Doc) -> ViewportLockRequest:
    sources = tuple(snapshot(item) for item in doc.entities[1:])
    return ViewportLockRequest(
        document_id=doc.Name,
        viewports=sources,
        exact_results=tuple(result(item) for item in sources),
    )


def all_request(doc: Doc) -> AllViewportLockRequest:
    base = selected_request(doc)
    return AllViewportLockRequest(
        **base.model_dump(),
        layout_name="Layout1",
        layout_revision="layout-1",
        complete_viewport_handles=("V1", "V2"),
    )


def approved_vl(preview: dict[str, Any], request: ViewportLockRequest) -> live.LiveVLExecuteRequest:
    return live.LiveVLExecuteRequest(
        request=request,
        expected_sources=tuple(live.LiveViewportEvidence.model_validate(item) for item in preview["expected_sources"]),
        approval_fingerprint=preview["approval_fingerprint"],
    )


def approved_vll(preview: dict[str, Any], request: AllViewportLockRequest) -> live.LiveVLLExecuteRequest:
    return live.LiveVLLExecuteRequest(
        request=request,
        expected_sources=tuple(live.LiveViewportEvidence.model_validate(item) for item in preview["expected_sources"]),
        approval_fingerprint=preview["approval_fingerprint"],
    )


def test_vl_locks_selected_viewports_with_undo_and_postcondition(doc: Doc) -> None:
    request = selected_request(doc)
    preview = live.preview_live_vl(request)
    assert preview["live_executable"] and preview["mutation"]
    executed = live.execute_live_vl(approved_vl(preview, request))
    assert executed.command_alias == "VL" and executed.changed_handles == ("V1", "V2")
    assert doc.marks == ["start", "end"] and executed.postcondition_verified
    assert all(item.DisplayLocked for item in doc.entities[1:])
    assert doc.entities[1].Center == (50.0, 40.0, 0.0)


def test_vll_requires_complete_live_layout_and_locks_all(doc: Doc) -> None:
    request = all_request(doc)
    preview = live.preview_live_vll(request)
    executed = live.execute_live_vll(approved_vll(preview, request))
    assert executed.command_alias == "VLL" and executed.changed_handles == ("V1", "V2")
    for item in doc.entities[1:]:
        item.DisplayLocked = False
    doc.entities.append(Viewport("V3", (300.0, 40.0, 0.0), 4))
    with pytest.raises(ValueError, match="complete live layout"):
        live.preview_live_vll(request)


def test_lock_rejects_semantic_expansion_bad_fingerprint_and_stale_source(doc: Doc) -> None:
    request = selected_request(doc)
    moved = request.exact_results[0].exact_viewport.model_copy(update={"center": Point3D(x=999.0, y=40.0)})
    expanded_result = request.exact_results[0].model_copy(update={"exact_viewport": moved})
    expanded = request.model_copy(update={"exact_results": (expanded_result, request.exact_results[1])})
    with pytest.raises(ValueError, match="only DisplayLocked"):
        live.preview_live_vl(expanded)

    preview = live.preview_live_vl(request)
    wrapped = approved_vl(preview, request)
    with pytest.raises(ValueError, match="fingerprint"):
        live.execute_live_vl(wrapped.model_copy(update={"approval_fingerprint": "sha256:" + "0" * 64}))
    doc.entities[1].Width = 101.0
    with pytest.raises(ValueError, match="no longer matches"):
        live.execute_live_vl(wrapped)


def test_lock_rejects_locked_layer_and_xref(doc: Doc) -> None:
    request = selected_request(doc)
    doc.Layers.items["VIEWPORTS"].Lock = True
    with pytest.raises(ValueError, match="locked or xref"):
        live.preview_live_vl(request)
    doc.Layers.items["VIEWPORTS"].Lock = False
    doc.entities[1].Layer = "XREF|VIEWPORTS"
    doc.Layers.items["XREF|VIEWPORTS"] = Layer("XREF|VIEWPORTS")
    with pytest.raises(ValueError, match="locked or xref"):
        live.preview_live_vl(request)


def test_help_backed_complex_operations_remain_preview_only() -> None:
    assert set(live.BLOCKED) == {"RBP", "WSL", "XCX", "XRC", "XRR", "P2M", "VA", "VGL", "VMO", "VPP"}
    assert live.HELP_URLS["RBP"] == "https://izzarder.com/335"
    assert "VISRETAIN" in live.BLOCKED["XRR"]
    assert "ExportLayout/ChSpace" in live.BLOCKED["P2M"]
    assert "paper setup" in live.BLOCKED["VMO"]
    assert "freeze/thaw" in live.BLOCKED["VPP"]


def test_registers_twelve_previews_and_only_two_viewport_lock_executes() -> None:
    class MCP:
        def __init__(self) -> None:
            self.names: list[str] = []

        def tool(self, *, name: str, annotations: Any) -> Any:
            del annotations
            self.names.append(name)
            return lambda function: function

    mcp = MCP()
    live.register_live_batch29_tools(mcp)  # type: ignore[arg-type]
    assert len([name for name in mcp.names if "preview" in name]) == 12
    assert [name for name in mcp.names if "execute" in name] == [
        "xicad_execute_live_vl",
        "xicad_execute_live_vll",
    ]
