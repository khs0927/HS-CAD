from __future__ import annotations

from math import hypot
from typing import Any

import pytest

from xicad_mcp import live_batch22 as live
from xicad_mcp.headless_core_batch1 import Point3D
from xicad_mcp.headless_core_batch22a import (
    BoundingBox3D,
    OffsetBasis,
    OffsetCurrentLayerRequest,
    OffsetMultiRequest,
    RandomCopyRequest,
    RotateMultiRequest,
    RotationTarget,
    SolidMoveBackRequest,
    ToleranceOffsetRequest,
)
from xicad_mcp.headless_core_batch22b import (
    AnnotationEntityType,
    BoundingBox,
    BoxMoveRequest,
    DboxAutoCopyRequest,
    DynamicScaleRequest,
    FrameEvidence,
    ProposedLine,
    ProposedScaleAnnotation,
    ScaleAnchor,
    ScaleItem,
    ScaleMultiRequest,
    SequentialScaleItem,
    SequentialScaleRequest,
    SourceDisposition,
    WallRecoverRequest,
)


class Layer:
    def __init__(self, name: str) -> None:
        self.Name, self.Color, self.Linetype, self.Lineweight, self.Lock = name, 7, "Continuous", -3, False


class Layers:
    def __init__(self) -> None:
        self.items = {name.casefold(): Layer(name) for name in ("SRC", "OUT", "CURRENT")}

    def Item(self, name: str) -> Layer:
        return self.items[name.casefold()]


class Line:
    ObjectName = "AcDbLine"

    def __init__(self, doc: Doc, handle: str, start: Any, end: Any, layer: str = "SRC") -> None:
        self.doc = doc
        self.Handle, self.StartPoint, self.EndPoint, self.Layer = handle, start, end, layer
        self.Color, self.Linetype, self.Lineweight, self.Thickness = 2, "Continuous", 25, 0.5

    def Copy(self) -> Line:
        item = self.doc.new_line(self.StartPoint, self.EndPoint, self.Layer)
        item.Color, item.Linetype = self.Color, self.Linetype
        item.Lineweight, item.Thickness = self.Lineweight, self.Thickness
        return item

    def Delete(self) -> None:
        self.doc.entities.remove(self)

    def Offset(self, distance: float) -> tuple[Line]:
        dx, dy = self.EndPoint[0] - self.StartPoint[0], self.EndPoint[1] - self.StartPoint[1]
        length = hypot(dx, dy)
        shift = (-dy * distance / length, dx * distance / length, 0.0)
        item = self.Copy()
        item.StartPoint = tuple(a + b for a, b in zip(self.StartPoint, shift, strict=True))
        item.EndPoint = tuple(a + b for a, b in zip(self.EndPoint, shift, strict=True))
        return (item,)


class Space:
    def __init__(self, doc: Doc) -> None:
        self.doc = doc

    def AddLine(self, start: Any, end: Any) -> Line:
        return self.doc.new_line(start, end, "0")


class Doc:
    Name = "Drawing1.dwg"

    def __init__(self) -> None:
        self.Layers, self.entities, self.marks = Layers(), [], []
        self.ModelSpace = Space(self)
        self.entities.extend(
            (
                Line(self, "A", (0.0, 0.0, 0.0), (10.0, 0.0, 0.0)),
                Line(self, "B", (0.0, 10.0, 0.0), (10.0, 10.0, 0.0)),
                Line(self, "X", (5.0, 0.0, 0.0), (5.0, 10.0, 0.0)),
            )
        )

    def new_line(self, start: Any, end: Any, layer: str) -> Line:
        item = Line(self, f"N{len(self.entities)}", start, end, layer)
        self.entities.append(item)
        return item

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


def approved(preview: dict[str, Any], request: Any) -> live.LiveBatch22ExecuteRequest:
    return live.LiveBatch22ExecuteRequest(
        request=request,
        expected_sources=tuple(live.LiveLineEvidence.model_validate(item) for item in preview["expected_sources"]),
        expected_target_layers=tuple(
            live.LiveLayerEvidence.model_validate(item) for item in preview["expected_target_layers"]
        ),
        approval_fingerprint=preview["approval_fingerprint"],
    )


def test_om_chains_exact_line_offsets_and_preserves_properties(doc: Doc) -> None:
    request = OffsetMultiRequest(
        document_id=doc.Name,
        source_handle="A",
        signed_distances=(2, 3),
        basis=OffsetBasis.PREVIOUS_RESULT,
        target_layer="OUT",
    )
    preview = live.preview_live_om(request)
    result = live.execute_live_batch22(approved(preview, request))
    assert result.created_handles == ("N3", "N4")
    assert doc.entities[-1].StartPoint == pytest.approx((0, 5, 0))
    assert (doc.entities[-1].Layer, doc.entities[-1].Color, doc.entities[-1].Thickness) == ("OUT", 2, 0.5)
    assert doc.marks == ["start", "end"]


def test_oo_stale_source_and_target_layer_are_rejected(doc: Doc) -> None:
    request = OffsetCurrentLayerRequest(
        document_id=doc.Name, source_handles=("A",), signed_distance=4, current_layer="CURRENT"
    )
    preview = live.preview_live_oo(request)
    wrapped = approved(preview, request)
    doc.entities[0].EndPoint = (11.0, 0.0, 0.0)
    with pytest.raises(ValueError, match="source state"):
        live.execute_live_batch22(wrapped)
    doc.entities[0].EndPoint = (10.0, 0.0, 0.0)
    doc.Layers.Item("CURRENT").Color = 3
    with pytest.raises(ValueError, match="target-layer state"):
        live.execute_live_batch22(wrapped)


def test_rm_rotates_copy_about_each_explicit_center(doc: Doc) -> None:
    request = RotateMultiRequest(
        document_id=doc.Name,
        targets=(RotationTarget(handle="A", center=Point3D(x=0, y=0)),),
        angle_degrees=90,
        keep_originals=True,
    )
    preview = live.preview_live_rm(request)
    result = live.execute_live_batch22(approved(preview, request))
    assert result.created_handles == ("N3",)
    assert doc.entities[-1].EndPoint == pytest.approx((0, 10, 0), abs=1e-10)


def test_sm_scales_line_about_recovered_anchor(doc: Doc) -> None:
    request = ScaleMultiRequest(
        document_id=doc.Name,
        items=(
            ScaleItem(
                handle="A",
                bounds=BoundingBox(minimum=Point3D(x=0, y=0), maximum=Point3D(x=10, y=2)),
                insertion_or_start=Point3D(x=0, y=0),
            ),
        ),
        factor=2,
        anchor=ScaleAnchor.LEFT_BOTTOM,
    )
    preview = live.preview_live_sm(request)
    result = live.execute_live_batch22(approved(preview, request))
    assert result.changed_handles == ("A",)
    assert doc.entities[0].EndPoint == (20, 0, 0)


def test_ot_and_ss_execute_every_guarded_geometry_branch(doc: Doc) -> None:
    tolerance = ToleranceOffsetRequest(
        document_id=doc.Name,
        source_handles=("A",),
        lower_signed_distance=-2,
        upper_signed_distance=3,
        target_layer="OUT",
    )
    result = live.execute_live_batch22(approved(live.preview_live_ot(tolerance), tolerance))
    assert result.created_handles == ("N3", "N4")
    assert [item.StartPoint for item in doc.entities[-2:]] == [(0, -2, 0), (0, 3, 0)]

    sequential = SequentialScaleRequest(
        document_id=doc.Name,
        items=(SequentialScaleItem(handle="B", base_point=Point3D(x=0, y=10)),),
        remembered_factor=0.5,
    )
    result = live.execute_live_batch22(approved(live.preview_live_ss(sequential), sequential))
    assert result.changed_handles == ("B",)
    assert doc.entities[1].EndPoint == (5, 10, 0)


def test_wr_creates_approved_line_and_deletes_only_intermediate(doc: Doc) -> None:
    request = WallRecoverRequest(
        document_id=doc.Name,
        boundary_line_handles=("A", "B"),
        intermediate_delete_handles=("X",),
        proposed_lines=(
            ProposedLine(
                source_boundary_handles=("A", "B"),
                start=Point3D(x=0, y=5),
                end=Point3D(x=10, y=5),
                layer="OUT",
            ),
        ),
    )
    preview = live.preview_live_wr(request)
    result = live.execute_live_batch22(approved(preview, request))
    assert result.created_handles == ("N3",) and result.erased_handles == ("X",)
    assert {item.Handle for item in doc.entities} == {"A", "B", "N3"}
    assert doc.entities[-1].Layer == "OUT"


def test_bmt_moves_and_dbc_copies_only_approved_line_geometry(doc: Doc) -> None:
    move = BoxMoveRequest(
        document_id=doc.Name,
        source_handles=("A",),
        source_reference=Point3D(x=0, y=0),
        target_reference=Point3D(x=100, y=20),
        disposition=SourceDisposition.MOVE,
    )
    live.execute_live_batch22(approved(live.preview_live_bmt(move), move))
    assert doc.entities[0].StartPoint == (100, 20, 0)

    copy = DboxAutoCopyRequest(
        document_id=doc.Name,
        frame=FrameEvidence(
            frame_handle="B",
            frame_bounds=BoundingBox(minimum=Point3D(x=0, y=0), maximum=Point3D(x=10, y=10)),
            source_reference=Point3D(x=0, y=0),
        ),
        source_entity_handles=("B",),
        target_reference_points=(Point3D(x=50, y=50), Point3D(x=100, y=100)),
    )
    result = live.execute_live_batch22(approved(live.preview_live_dbc(copy), copy))
    assert len(result.created_handles) == 2
    assert [item.StartPoint for item in doc.entities[-2:]] == [(50, 60, 0), (100, 110, 0)]


def test_rdc_sb_and_das_are_preview_only_with_explicit_blockers() -> None:
    rdc = RandomCopyRequest(
        document_id="D",
        source_handles=("A",),
        bounds=BoundingBox3D(minimum=Point3D(x=0, y=0), maximum=Point3D(x=10, y=10)),
        copy_count=1,
        seed="fixed",
    )
    sb = SolidMoveBackRequest(
        document_id="D", target_handles=("H",), entity_types={"H": "HATCH"}, mode="bottom"
    )
    das = DynamicScaleRequest(
        document_id="D",
        scale_denominator=100,
        exact_annotations=(
            ProposedScaleAnnotation(
                entity_type=AnnotationEntityType.TEXT,
                insertion_point=Point3D(x=0, y=0),
                layer="0",
                text="1:100",
                text_height=2.5,
            ),
        ),
    )
    previews = (live.preview_live_rdc(rdc), live.preview_live_sb(sb), live.preview_live_das(das))
    assert all(not item["mutation"] and not item["live_executable"] for item in previews)
    assert all(item["blocked_reason"] for item in previews)


def test_fingerprint_tampering_and_tool_registration(doc: Doc) -> None:
    request = OffsetCurrentLayerRequest(
        document_id=doc.Name, source_handles=("A",), signed_distance=2, current_layer="CURRENT"
    )
    wrapped = approved(live.preview_live_oo(request), request).model_copy(
        update={"approval_fingerprint": "sha256:" + "0" * 64}
    )
    with pytest.raises(ValueError, match="fingerprint"):
        live.execute_live_batch22(wrapped)

    class MCP:
        def __init__(self) -> None:
            self.names: list[str] = []

        def tool(self, *, name: str, annotations: Any) -> Any:
            del annotations
            self.names.append(name)
            return lambda function: function

    mcp = MCP()
    live.register_live_batch22_tools(mcp)  # type: ignore[arg-type]
    assert len(mcp.names) == 21
    assert len([name for name in mcp.names if "execute" in name]) == 9
    assert not any(f"execute_live_{alias}" in mcp.names for alias in ("rdc", "sb", "das"))
