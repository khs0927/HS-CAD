from __future__ import annotations

from typing import Any

import pytest

from xicad_mcp import live_batch23 as live
from xicad_mcp.headless_core_batch1 import Point3D
from xicad_mcp.headless_core_batch23a import (
    DrawingUnit,
    FindFrameScaleRequest,
    FrameExtent,
    FramePlacement,
    FrameSortRequest,
    NumberingTarget,
    PaperSize,
    TitleNumberingRequest,
)


class Layer:
    def __init__(self, name: str) -> None:
        self.Name, self.Lock = name, False


class Layers:
    def __init__(self) -> None:
        self.items = {"FRAME": Layer("FRAME"), "TEXT": Layer("TEXT")}

    def Item(self, name: str) -> Layer:
        return self.items[name]


class Attribute:
    ObjectName = "AcDbAttribute"

    def __init__(self, handle: str, tag: str, text: str) -> None:
        self.Handle, self.TagString, self.TextString, self.Layer = handle, tag, text, "TEXT"


class BlockReference:
    ObjectName = "AcDbBlockReference"

    def __init__(self, handle: str, insertion: tuple[float, float, float], attributes: list[Attribute]) -> None:
        self.Handle, self.InsertionPoint, self.attributes = handle, insertion, attributes
        self.Layer, self.Name, self.EffectiveName = "FRAME", "FRAME_DEF", "FRAME_DEF"
        self.Rotation = 0.0
        self.XScaleFactor = self.YScaleFactor = self.ZScaleFactor = 1.0

    def GetAttributes(self) -> list[Attribute]:
        return self.attributes


class Doc:
    Name = "Drawing1.dwg"

    def __init__(self) -> None:
        self.Layers = Layers()
        self.entities = [
            BlockReference("B1", (0.0, 0.0, 0.0), [Attribute("A1", "NO", "OLD")]),
            BlockReference("B2", (20.0, 0.0, 0.0), [Attribute("A2", "NO", "OLD")]),
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
    monkeypatch.setattr(live, "_entities", lambda _doc: {item.Handle.casefold(): item for item in drawing.entities})
    monkeypatch.setattr(live, "_variant", lambda point: (point.x, point.y, point.z))
    return drawing


def approved(preview: dict[str, Any], request: Any) -> live.LiveBatch23ExecuteRequest:
    return live.LiveBatch23ExecuteRequest(
        request=request,
        expected_blocks=tuple(live.LiveBlockReferenceEvidence.model_validate(item) for item in preview["expected_blocks"]),
        expected_attributes=tuple(
            live.LiveAttributeEvidence.model_validate(item) for item in preview["expected_attributes"]
        ),
        approval_fingerprint=preview["approval_fingerprint"],
    )


def test_dbs_preview_execute_moves_exact_block_references(doc: Doc) -> None:
    request = FrameSortRequest(
        document_id=doc.Name,
        placements=(
            FramePlacement(
                block_reference_handle="B1",
                source_anchor=Point3D(x=0, y=0),
                target_anchor=Point3D(x=100, y=50),
            ),
            FramePlacement(
                block_reference_handle="B2",
                source_anchor=Point3D(x=20, y=0),
                target_anchor=Point3D(x=200, y=50),
            ),
        ),
    )
    preview = live.preview_live_dbs(request)
    result = live.execute_live_batch23(approved(preview, request))
    assert result.command_alias == "DBS" and result.changed_handles == ("B1", "B2")
    assert [item.InsertionPoint for item in doc.entities] == [(100, 50, 0), (200, 50, 0)]
    assert doc.marks == ["start", "end"] and result.postcondition_verified


def test_dbs_rejects_mismatched_anchor_before_approval(doc: Doc) -> None:
    request = FrameSortRequest(
        document_id=doc.Name,
        placements=(
            FramePlacement(
                block_reference_handle="B1",
                source_anchor=Point3D(x=1, y=0),
                target_anchor=Point3D(x=100, y=50),
            ),
        ),
    )
    with pytest.raises(ValueError, match="source anchor"):
        live.preview_live_dbs(request)


def test_tn_preview_execute_updates_exact_writable_attributes(doc: Doc) -> None:
    request = TitleNumberingRequest(
        document_id=doc.Name,
        ordered_targets=(
            NumberingTarget(block_reference_handle="B1", attribute_handle="A1", attribute_tag="NO", old_text="OLD"),
            NumberingTarget(block_reference_handle="B2", attribute_handle="A2", attribute_tag="NO", old_text="OLD"),
        ),
        prefix="D-",
        starting_number=7,
        step=2,
        zero_pad_width=3,
    )
    preview = live.preview_live_tn(request)
    result = live.execute_live_batch23(approved(preview, request))
    assert result.command_alias == "TN" and result.changed_handles == ("A1", "A2")
    assert [block.attributes[0].TextString for block in doc.entities] == ["D-007", "D-009"]


def test_tn_stale_attribute_and_bad_fingerprint_are_rejected(doc: Doc) -> None:
    request = TitleNumberingRequest(
        document_id=doc.Name,
        ordered_targets=(
            NumberingTarget(block_reference_handle="B1", attribute_handle="A1", attribute_tag="NO", old_text="OLD"),
        ),
        starting_number=1,
        step=1,
    )
    preview = live.preview_live_tn(request)
    wrapped = approved(preview, request)
    doc.entities[0].attributes[0].TextString = "STALE"
    with pytest.raises(ValueError, match="attribute state no longer matches"):
        live.execute_live_batch23(wrapped)
    doc.entities[0].attributes[0].TextString = "OLD"
    bad = wrapped.model_copy(update={"approval_fingerprint": "sha256:" + "0" * 64})
    with pytest.raises(ValueError, match="fingerprint"):
        live.execute_live_batch23(bad)


def test_dfs_preview_is_non_mutating_and_explains_blocker() -> None:
    request = FindFrameScaleRequest(
        document_id="Drawing1.dwg",
        frames=(FrameExtent(block_reference_handle="B1", width=841, height=594),),
        paper_size=PaperSize.A1,
        drawing_unit=DrawingUnit.MILLIMETER,
        allow_rotated_sheet=False,
    )
    preview = live.preview_live_dfs(request)
    assert preview["command_alias"] == "DFS"
    assert not preview["mutation"] and not preview["live_executable"]
    assert "unrecovered" in preview["blocked_reason"]


def test_registers_twelve_previews_and_only_dbs_tn_execute() -> None:
    class MCP:
        def __init__(self) -> None:
            self.names: list[str] = []

        def tool(self, *, name: str, annotations: Any) -> Any:
            del annotations
            self.names.append(name)
            return lambda function: function

    mcp = MCP()
    live.register_live_batch23_tools(mcp)  # type: ignore[arg-type]
    previews = [name for name in mcp.names if "preview" in name]
    executes = [name for name in mcp.names if "execute" in name]
    assert len(previews) == 12
    assert executes == ["xicad_execute_live_dbs", "xicad_execute_live_tn"]
    assert all(alias in " ".join(previews) for alias in ("dbs", "dfs", "dsb", "mdl", "pbs", "tn", "tob", "zr", "ae", "ahm", "ba", "cdb"))
