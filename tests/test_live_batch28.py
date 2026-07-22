from __future__ import annotations

from typing import Any

import pytest

from xicad_mcp import live_batch28 as live
from xicad_mcp.headless_core_batch1 import Point3D
from xicad_mcp.headless_core_batch28a import (
    BlockReferenceSnapshot,
    ChangeBlockScaleRequest,
    ExactBlockReference,
)


class Layer:
    def __init__(self, name: str, locked: bool = False) -> None:
        self.Name, self.Lock = name, locked


class Layers:
    def __init__(self) -> None:
        self.items = {name: Layer(name) for name in ("BLOCKS", "OUTPUT")}

    def Item(self, name: str) -> Layer:
        return self.items[name]


class Definition:
    IsXRef = False


class Definitions:
    def Item(self, _name: str) -> Definition:
        return Definition()


class BlockReference:
    ObjectName = "AcDbBlockReference"

    def __init__(self, handle: str, point: tuple[float, float, float]) -> None:
        self.Handle, self.Name, self.EffectiveName = handle, "CHAIR", "CHAIR"
        self.InsertionPoint, self.Rotation = point, 0.0
        self.XScaleFactor, self.YScaleFactor, self.ZScaleFactor = 1.0, 1.0, 1.0
        self.Layer = "BLOCKS"


class Doc:
    Name = "Drawing1.dwg"

    def __init__(self) -> None:
        self.Layers, self.Blocks = Layers(), Definitions()
        self.entities = [BlockReference("B1", (0.0, 0.0, 0.0)), BlockReference("B2", (10.0, 5.0, 0.0))]
        self.marks: list[str] = []

    def StartUndoMark(self) -> None:
        self.marks.append("start")

    def EndUndoMark(self) -> None:
        self.marks.append("end")


@pytest.fixture
def doc(monkeypatch: pytest.MonkeyPatch) -> Doc:
    drawing = Doc()
    monkeypatch.setattr(live, "_drawing", lambda _name: drawing)
    monkeypatch.setattr(live, "_entities", lambda _doc: {item.Handle.casefold(): item for item in drawing.entities})
    return drawing


def request_for(doc: Doc) -> ChangeBlockScaleRequest:
    references = tuple(
        BlockReferenceSnapshot(
            handle=item.Handle,
            reference_revision=f"source-{item.Handle}",
            block_name=item.Name,
            definition_revision="definition-CHAIR",
            insertion_point=Point3D(x=item.InsertionPoint[0], y=item.InsertionPoint[1]),
            rotation_radians=item.Rotation,
            scale_x=item.XScaleFactor,
            scale_y=item.YScaleFactor,
            scale_z=item.ZScaleFactor,
            layer=item.Layer,
            count_key="CHAIR",
        )
        for item in doc.entities
    )
    results = tuple(
        ExactBlockReference(
            source_handle=item.Handle,
            source_revision=f"source-{item.Handle}",
            result_revision=f"result-{item.Handle}",
            block_name=item.Name,
            insertion_point=Point3D(x=item.InsertionPoint[0], y=item.InsertionPoint[1]),
            rotation_radians=0.0,
            scale_x=2.0,
            scale_y=3.0,
            scale_z=1.0,
            layer="BLOCKS",
        )
        for item in doc.entities
    )
    return ChangeBlockScaleRequest(document_id=doc.Name, references=references, exact_results=results)


def approved(preview: dict[str, Any], request: ChangeBlockScaleRequest) -> live.LiveBSCExecuteRequest:
    return live.LiveBSCExecuteRequest(
        request=request,
        expected_sources=tuple(
            live.LiveBlockReferenceEvidence.model_validate(item) for item in preview["expected_sources"]
        ),
        approval_fingerprint=preview["approval_fingerprint"],
    )


def test_bsc_applies_exact_reference_state_with_undo_and_postcondition(doc: Doc) -> None:
    request = request_for(doc)
    preview = live.preview_live_bsc(request)
    assert preview["live_executable"] and preview["mutation"]
    result = live.execute_live_bsc(approved(preview, request))
    assert result.command_alias == "BSC" and result.changed_handles == ("B1", "B2")
    assert doc.marks == ["start", "end"] and result.postcondition_verified
    assert doc.entities[0].InsertionPoint == (0.0, 0.0, 0.0)
    assert (doc.entities[0].XScaleFactor, doc.entities[0].YScaleFactor, doc.entities[0].ZScaleFactor) == (
        2.0,
        3.0,
        1.0,
    )
    assert doc.entities[0].Rotation == 0.0 and doc.entities[0].Layer == "BLOCKS"


def test_bsc_rejects_non_scale_semantic_expansion(doc: Doc) -> None:
    request = request_for(doc)
    moved = request.exact_results[0].model_copy(update={"insertion_point": Point3D(x=99.0, y=99.0)})
    expanded = request.model_copy(update={"exact_results": (moved, request.exact_results[1])})
    with pytest.raises(ValueError, match="only official-help X/Y"):
        live.preview_live_bsc(expanded)


def test_bsc_rejects_bad_fingerprint_stale_source_locked_layer_and_xref(doc: Doc) -> None:
    request = request_for(doc)
    preview = live.preview_live_bsc(request)
    wrapped = approved(preview, request)
    with pytest.raises(ValueError, match="fingerprint"):
        live.execute_live_bsc(wrapped.model_copy(update={"approval_fingerprint": "sha256:" + "0" * 64}))
    doc.entities[0].XScaleFactor = 1.5
    with pytest.raises(ValueError, match="no longer matches"):
        live.execute_live_bsc(wrapped)
    doc.entities[0].XScaleFactor = 1.0
    doc.Layers.items["BLOCKS"].Lock = True
    with pytest.raises(ValueError, match="locked or xref"):
        live.preview_live_bsc(request)
    doc.Layers.items["BLOCKS"].Lock = False
    doc.entities[0].Layer = "XREF|BLOCKS"
    doc.Layers.items["XREF|BLOCKS"] = Layer("XREF|BLOCKS")
    with pytest.raises(ValueError, match="locked or xref"):
        live.preview_live_bsc(request)


def test_multi_file_export_xclip_and_compiled_block_operations_remain_preview_only() -> None:
    assert set(live.BLOCKED) == {"BLX", "BQT", "BRM", "BRN", "CX", "EAR", "M2B", "MFB", "MFX", "MX", "QWB"}
    assert "multi-file" in live.BLOCKED["MFB"]
    assert "XCLIP" in live.BLOCKED["MX"]
    assert "atomic export" in live.BLOCKED["QWB"]


def test_registers_twelve_previews_and_only_bsc_execute() -> None:
    class MCP:
        def __init__(self) -> None:
            self.names: list[str] = []

        def tool(self, *, name: str, annotations: Any) -> Any:
            del annotations
            self.names.append(name)
            return lambda function: function

    mcp = MCP()
    live.register_live_batch28_tools(mcp)  # type: ignore[arg-type]
    assert len([name for name in mcp.names if "preview" in name]) == 12
    assert [name for name in mcp.names if "execute" in name] == ["xicad_execute_live_bsc"]
