from __future__ import annotations

import math
from typing import Any

import pytest

from xicad_mcp import live_batch32 as live
from xicad_mcp.headless_core_batch32 import (
    EntitySnapshot,
    ExactChangeSet,
    ExactEntityResult,
    Point3D,
    ReferenceRotateRequest,
)

DIGEST_A = "sha256:" + "a" * 64
DIGEST_B = "sha256:" + "b" * 64


class Layer:
    def __init__(self, locked: bool = False) -> None:
        self.Lock = locked


class Layers:
    def __init__(self) -> None:
        self.items = {"A-TEXT": Layer(), "A-BLOCK": Layer()}

    def Item(self, name: str) -> Layer:
        return self.items[name]


class Definition:
    def __init__(self, xref: bool = False) -> None:
        self.IsXRef = xref


class Blocks:
    def __init__(self) -> None:
        self.items = {"CHAIR": Definition()}

    def Item(self, name: str) -> Definition:
        return self.items[name]


class Entity:
    def __init__(
        self,
        handle: str,
        point: tuple[float, float, float],
        *,
        object_name: str = "AcDbText",
        layer: str = "A-TEXT",
    ) -> None:
        self.Handle, self.ObjectName, self.Layer = handle, object_name, layer
        self.InsertionPoint, self.Rotation = point, 0.0
        self.Name = self.EffectiveName = "CHAIR"
        self.fail = False
        self.ignore = False

    def Rotate(self, base: tuple[float, float, float], angle: float) -> None:
        if self.fail:
            raise RuntimeError("injected rotate failure")
        if self.ignore:
            return
        dx, dy = self.InsertionPoint[0] - base[0], self.InsertionPoint[1] - base[1]
        cosine, sine = math.cos(angle), math.sin(angle)
        self.InsertionPoint = (
            base[0] + dx * cosine - dy * sine,
            base[1] + dx * sine + dy * cosine,
            self.InsertionPoint[2],
        )
        self.Rotation += angle


class Doc:
    Name = "Drawing1.dwg"

    def __init__(self) -> None:
        self.Layers, self.Blocks = Layers(), Blocks()
        self.entities = {
            "10": Entity("10", (10.0, 0.0, 0.0)),
            "11": Entity("11", (20.0, 0.0, 0.0), object_name="AcDbBlockReference", layer="A-BLOCK"),
        }
        self.marks: list[str] = []

    def HandleToObject(self, handle: str) -> Entity:
        return self.entities[handle]

    def StartUndoMark(self) -> None: self.marks.append("start")
    def EndUndoMark(self) -> None: self.marks.append("end")


def rr_request(doc: Doc) -> ReferenceRotateRequest:
    sources = tuple(
        EntitySnapshot(
            handle=item.Handle,
            revision=f"source-{item.Handle}",
            entity_type=item.ObjectName,
            state_digest=DIGEST_A,
        )
        for item in doc.entities.values()
    )
    changes = ExactChangeSet(
        source_revisions=tuple(item.revision for item in sources),
        created_or_updated=tuple(
            ExactEntityResult(
                result_id=item.Handle,
                entity_type=item.ObjectName,
                layer=item.Layer,
                state_digest=DIGEST_B,
            )
            for item in doc.entities.values()
        ),
        manifest_digest=DIGEST_B,
    )
    return ReferenceRotateRequest(
        document_id=doc.Name,
        sources=sources,
        base_point=Point3D(x=0, y=0),
        reference_start=Point3D(x=100, y=100),
        reference_end=Point3D(x=200, y=100),
        destination_start=Point3D(x=-50, y=30),
        destination_end=Point3D(x=-50, y=130),
        exact_changes=changes,
    )


def approved(preview: dict[str, Any], request: ReferenceRotateRequest) -> live.LiveRRExecuteRequest:
    return live.LiveRRExecuteRequest(
        request=request,
        expected_sources=tuple(
            live.LiveRREntityEvidence.model_validate(item) for item in preview["expected_sources"]
        ),
        approval_fingerprint=preview["approval_fingerprint"],
    )


def test_rr_rotates_about_independent_base_with_undo_and_postconditions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    doc = Doc()
    monkeypatch.setattr(live, "_drawing", lambda _name: doc)
    request = rr_request(doc)
    preview = live.preview_live_rr(request)
    assert preview["live_executable"] and preview["mutation"]
    result = live.execute_live_rr(approved(preview, request))
    assert result.changed_handles == ("10", "11")
    assert result.rotation_delta_radians == pytest.approx(math.pi / 2)
    assert doc.entities["10"].InsertionPoint == pytest.approx((0.0, 10.0, 0.0))
    assert doc.entities["11"].InsertionPoint == pytest.approx((0.0, 20.0, 0.0))
    assert doc.entities["10"].Rotation == pytest.approx(math.pi / 2)
    assert doc.marks == ["start", "end"] and result.postcondition_verified


def test_rr_rejects_bad_fingerprint_stale_state_locked_layer_and_xref(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    doc = Doc()
    monkeypatch.setattr(live, "_drawing", lambda _name: doc)
    request = rr_request(doc)
    preview = live.preview_live_rr(request)
    wrapped = approved(preview, request)
    with pytest.raises(ValueError, match="fingerprint"):
        live.execute_live_rr(
            wrapped.model_copy(update={"approval_fingerprint": "sha256:" + "0" * 64})
        )
    doc.entities["10"].Rotation = 0.25
    with pytest.raises(ValueError, match="no longer matches"):
        live.execute_live_rr(wrapped)
    doc.entities["10"].Rotation = 0.0
    doc.Layers.Item("A-TEXT").Lock = True
    with pytest.raises(ValueError, match="locked or xref"):
        live.preview_live_rr(request)
    doc.Layers.Item("A-TEXT").Lock = False
    doc.Blocks.Item("CHAIR").IsXRef = True
    with pytest.raises(ValueError, match="xref block"):
        live.preview_live_rr(request)


def test_rr_rejects_semantic_expansion_and_unsupported_entities(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    doc = Doc()
    monkeypatch.setattr(live, "_drawing", lambda _name: doc)
    request = rr_request(doc)
    erased = request.exact_changes.model_copy(update={"erased_handles": ("10",)})
    with pytest.raises(ValueError, match="cannot erase"):
        live.preview_live_rr(request.model_copy(update={"exact_changes": erased}))
    doc.entities["10"].ObjectName = "AcDbLine"
    with pytest.raises(ValueError, match="limited to text"):
        live.preview_live_rr(request)


def test_rr_rolls_back_prior_rotations_on_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    doc = Doc()
    monkeypatch.setattr(live, "_drawing", lambda _name: doc)
    request = rr_request(doc)
    preview = live.preview_live_rr(request)
    doc.entities["11"].fail = True
    with pytest.raises(RuntimeError, match="injected"):
        live.execute_live_rr(approved(preview, request))
    assert doc.entities["10"].InsertionPoint == pytest.approx((10.0, 0.0, 0.0))
    assert doc.entities["10"].Rotation == pytest.approx(0.0)
    assert doc.marks == ["start", "end"]


def test_rr_rolls_back_on_postcondition_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    doc = Doc()
    monkeypatch.setattr(live, "_drawing", lambda _name: doc)
    request = rr_request(doc)
    preview = live.preview_live_rr(request)
    doc.entities["11"].ignore = True
    with pytest.raises(RuntimeError, match="postcondition"):
        live.execute_live_rr(approved(preview, request))
    assert doc.entities["10"].InsertionPoint == pytest.approx((10.0, 0.0, 0.0))
    assert doc.entities["10"].Rotation == pytest.approx(0.0)
    assert doc.marks == ["start", "end"]


def test_batch32_registers_eleven_previews_and_only_rr_execute() -> None:
    class MCP:
        def __init__(self) -> None: self.names: list[str] = []
        def tool(self, *, name: str, annotations: Any) -> Any:
            del annotations
            self.names.append(name)
            return lambda function: function

    mcp = MCP()
    live.register_live_batch32_tools(mcp)  # type: ignore[arg-type]
    assert len([name for name in mcp.names if "preview" in name]) == 11
    assert [name for name in mcp.names if "execute" in name] == ["xicad_execute_live_rr"]
    assert set(live.BLOCKED) == {"CE", "BBB", "FF", "WQ", "WE", "XX", "Q11", "MK", "LII", "SLD"}
