from __future__ import annotations

from typing import Any

import pytest

from xicad_mcp import live_batch27 as live
from xicad_mcp.headless_core_batch1 import Point3D
from xicad_mcp.headless_core_batch27a import BlockReferenceSnapshot, LineBetweenBlocksRequest


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
    Rotation = 0.0
    XScaleFactor = 1.0
    YScaleFactor = 1.0
    ZScaleFactor = 1.0

    def __init__(self, handle: str, name: str, point: tuple[float, float, float]) -> None:
        self.Handle, self.Name, self.InsertionPoint = handle, name, point
        self.EffectiveName, self.Layer = name, "BLOCKS"


class Polyline:
    ObjectName = "AcDbPolyline"

    def __init__(self, handle: str, coordinates: tuple[float, ...]) -> None:
        self.Handle, self.Coordinates = handle, coordinates
        self.Layer, self.Closed = "0", False


class ModelSpace:
    def __init__(self, doc: Doc) -> None:
        self.doc = doc

    def AddLightWeightPolyline(self, coordinates: tuple[float, ...]) -> Polyline:
        entity = Polyline(f"N{len(self.doc.entities)}", coordinates)
        self.doc.entities.append(entity)
        return entity


class Doc:
    Name = "Drawing1.dwg"

    def __init__(self) -> None:
        self.Layers, self.Blocks = Layers(), Definitions()
        self.entities: list[Any] = [
            BlockReference("B1", "CHAIR", (0.0, 0.0, 0.0)),
            BlockReference("B2", "CHAIR", (10.0, 5.0, 0.0)),
            BlockReference("B3", "TABLE", (20.0, 0.0, 0.0)),
        ]
        self.ModelSpace = ModelSpace(self)
        self.marks: list[str] = []

    def StartUndoMark(self) -> None:
        self.marks.append("start")

    def EndUndoMark(self) -> None:
        self.marks.append("end")


def snapshot(entity: BlockReference, revision: str) -> BlockReferenceSnapshot:
    return BlockReferenceSnapshot(
        handle=entity.Handle,
        block_name=entity.Name,
        definition_revision=f"definition-{entity.Name}",
        reference_revision=revision,
        insertion_point=Point3D(x=entity.InsertionPoint[0], y=entity.InsertionPoint[1]),
        layer=entity.Layer,
    )


@pytest.fixture
def doc(monkeypatch: pytest.MonkeyPatch) -> Doc:
    drawing = Doc()
    monkeypatch.setattr(live, "_drawing", lambda _name: drawing)
    monkeypatch.setattr(live, "_entities", lambda _doc: {item.Handle.casefold(): item for item in drawing.entities})
    monkeypatch.setattr(
        live, "_variant_points", lambda points: tuple(value for point in points for value in (point.x, point.y))
    )
    return drawing


def request_for(doc: Doc) -> LineBetweenBlocksRequest:
    blocks = tuple(snapshot(item, f"revision-{index}") for index, item in enumerate(doc.entities, 1))
    return LineBetweenBlocksRequest(
        document_id=doc.Name,
        blocks=blocks,
        ordered_handles=("B2", "B1", "B3"),
        output_layer="OUTPUT",
        closed=False,
    )


def approved(preview: dict[str, Any], request: LineBetweenBlocksRequest) -> live.LiveBBLExecuteRequest:
    return live.LiveBBLExecuteRequest(
        request=request,
        expected_sources=tuple(live.LiveBlockEvidence.model_validate(item) for item in preview["expected_sources"]),
        expected_target_layer=live.LiveLayerEvidence.model_validate(preview["expected_target_layer"]),
        approval_fingerprint=preview["approval_fingerprint"],
    )


def test_bbl_creates_exact_ordered_polyline_with_undo_and_postcondition(doc: Doc) -> None:
    request = request_for(doc)
    preview = live.preview_live_bbl(request)
    assert preview["live_executable"] and preview["mutation"]
    result = live.execute_live_bbl(approved(preview, request))
    output = doc.entities[-1]
    assert result.command_alias == "BBL" and result.created_handles == ("N3",)
    assert output.Coordinates == (10.0, 5.0, 0.0, 0.0, 20.0, 0.0)
    assert output.Layer == "OUTPUT" and not output.Closed
    assert doc.marks == ["start", "end"] and result.postcondition_verified


def test_bbl_rejects_bad_fingerprint_stale_source_locked_layer_and_xref(doc: Doc) -> None:
    request = request_for(doc)
    preview = live.preview_live_bbl(request)
    wrapped = approved(preview, request)
    bad = wrapped.model_copy(update={"approval_fingerprint": "sha256:" + "0" * 64})
    with pytest.raises(ValueError, match="fingerprint"):
        live.execute_live_bbl(bad)
    doc.entities[1].InsertionPoint = (11.0, 5.0, 0.0)
    with pytest.raises(ValueError, match="no longer matches"):
        live.execute_live_bbl(wrapped)
    doc.entities[1].InsertionPoint = (10.0, 5.0, 0.0)
    doc.Layers.items["BLOCKS"].Lock = True
    with pytest.raises(ValueError, match="locked or xref"):
        live.preview_live_bbl(request)
    doc.Layers.items["BLOCKS"].Lock = False
    doc.entities[0].Layer = "XREF|BLOCKS"
    doc.Layers.items["XREF|BLOCKS"] = Layer("XREF|BLOCKS")
    with pytest.raises(ValueError, match="locked or xref"):
        live.preview_live_bbl(request)


def test_block_and_file_operations_remain_truthful_preview_only(doc: Doc) -> None:
    del doc
    # One representative guard plus the complete BLOCKED set prevents accidental
    # promotion of block-definition/xref/file-output semantics to a write tool.
    assert set(live.BLOCKED) == {"XZ", "ABX", "B2X", "BAD", "BAM", "BCC", "BCH", "BCO", "BEX", "BIN", "BLA"}
    assert "external DWG" in live.BLOCKED["B2X"]
    assert "atomic file-output" in live.BLOCKED["BEX"]


def test_registers_twelve_previews_and_only_bbl_execute() -> None:
    class MCP:
        def __init__(self) -> None:
            self.names: list[str] = []

        def tool(self, *, name: str, annotations: Any) -> Any:
            del annotations
            self.names.append(name)
            return lambda function: function

    mcp = MCP()
    live.register_live_batch27_tools(mcp)  # type: ignore[arg-type]
    assert len([name for name in mcp.names if "preview" in name]) == 12
    assert [name for name in mcp.names if "execute" in name] == ["xicad_execute_live_bbl"]
