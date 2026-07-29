from __future__ import annotations

from typing import Any

import pytest

from xicad_mcp import live_gap_25_32 as live
from xicad_mcp.headless_core_batch1 import Point3D
from xicad_mcp.headless_core_batch25b import (
    MaskMode,
    ProposedTextBoundary,
    TextBoxRequest,
    TextBoxShape,
    TextEntitySnapshot,
)
from xicad_mcp.headless_core_batch28a import (
    BlockDefinitionSnapshot,
    RenameBlocksRequest,
    RenameResult,
)
from xicad_mcp.headless_core_batch28a import (
    EntitySnapshot as BlockMemberSnapshot,
)

DIGEST_A = "sha256:" + "a" * 64


class Layer:
    def __init__(self, name: str) -> None:
        self.Name, self.Lock = name, False


class Collection:
    def __init__(self, items: dict[str, Any]) -> None:
        self.items = items

    def Item(self, name: str) -> Any:
        for key, value in self.items.items():
            if key.casefold() == name.casefold():
                return value
        raise KeyError(name)


class Entity:
    def __init__(self, handle: str, object_name: str, layer: str) -> None:
        self.Handle, self.ObjectName, self.Layer = handle, object_name, layer
        self.deleted = False

    def Delete(self) -> None:
        self.deleted = True


class Text(Entity):
    def __init__(self) -> None:
        super().__init__("T1", "AcDbText", "TEXT")
        self.TextString, self.StyleName, self.Height = "room", "Standard", 2.5
        self.bounds = ((0.0, 0.0, 0.0), (4.0, 2.0, 0.0))

    def GetBoundingBox(self) -> tuple[Any, Any]:
        return self.bounds


class Polyline(Entity):
    def __init__(self, handle: str, coordinates: tuple[float, ...]) -> None:
        super().__init__(handle, "AcDbPolyline", "0")
        self.Coordinates, self.Closed = coordinates, False


class Member(Entity):
    def __init__(self, handle: str) -> None:
        super().__init__(handle, "AcDbLine", "BLOCK")


class Block:
    def __init__(self, collection: Blocks, name: str, members: list[Member]) -> None:
        self._collection, self._name, self.members = collection, name, members
        self.IsXRef = self.IsLayout = False
        self.Origin = (0.0, 0.0, 0.0)
        self.fail_rename = False

    @property
    def Name(self) -> str:
        return self._name

    @Name.setter
    def Name(self, value: str) -> None:
        if self.fail_rename:
            raise RuntimeError("injected rename failure")
        self._collection.items.pop(self._name.casefold(), None)
        self._name = value
        self._collection.items[value.casefold()] = self

    def __iter__(self) -> Any:
        return iter(self.members)


class Blocks(Collection):
    def __init__(self) -> None:
        super().__init__({})

    def add(self, name: str, members: list[Member]) -> Block:
        block = Block(self, name, members)
        self.items[name.casefold()] = block
        return block


class ModelSpace:
    def __init__(self, doc: Doc) -> None:
        self.doc = doc

    def AddLightWeightPolyline(self, coordinates: tuple[float, ...]) -> Polyline:
        entity = Polyline(f"P{len(self.doc.entities)}", tuple(coordinates))
        self.doc.entities[entity.Handle] = entity
        return entity


class Doc:
    Name = "Drawing1.dwg"

    def __init__(self) -> None:
        self.Layers = Collection(
            {name: Layer(name) for name in ("0", "TEXT", "ANNO", "BLOCK")}
        )
        self.TextStyles = Collection({"Standard": object()})
        self.entities: dict[str, Entity] = {"T1": Text()}
        self.ModelSpace = ModelSpace(self)
        self.Blocks = Blocks()
        self.Blocks.add("OLD", [Member("B1")])
        self.marks: list[str] = []
        self.regens = 0

    def HandleToObject(self, handle: str) -> Entity:
        return self.entities[handle]

    def StartUndoMark(self) -> None:
        self.marks.append("start")

    def EndUndoMark(self) -> None:
        self.marks.append("end")

    def Regen(self, mode: int) -> None:
        assert mode == 1
        self.regens += 1


@pytest.fixture
def doc(monkeypatch: pytest.MonkeyPatch) -> Doc:
    drawing = Doc()
    monkeypatch.setattr(live, "_drawing", lambda _name: drawing)
    monkeypatch.setattr(
        live,
        "_lwpolyline",
        lambda space, vertices: space.AddLightWeightPolyline(
            tuple(value for point in vertices for value in (point.x, point.y))
        ),
    )
    return drawing


def tx_request(doc: Doc) -> TextBoxRequest:
    text = doc.entities["T1"]
    assert isinstance(text, Text)
    return TextBoxRequest(
        document_id=doc.Name,
        sources=(
            TextEntitySnapshot(
                handle=text.Handle,
                text=text.TextString,
                bounds_min=Point3D(x=0, y=0),
                bounds_max=Point3D(x=4, y=2),
                geometry_revision="text-r1",
            ),
        ),
        shape=TextBoxShape.RECTANGLE,
        uppercase=True,
        group_results=False,
        mask_mode=MaskMode.NONE,
        text_style="Standard",
        text_layer="TEXT",
        text_height=3,
        boundary_layer="ANNO",
        width_gap=1,
        height_gap=1,
        corner_radius=0,
        exact_boundaries=(
            ProposedTextBoundary(
                source_handle="T1",
                exact_vertices=(
                    Point3D(x=-1, y=-1),
                    Point3D(x=5, y=-1),
                    Point3D(x=5, y=3),
                    Point3D(x=-1, y=3),
                ),
                boundary_layer="ANNO",
            ),
        ),
    )


def brn_request(doc: Doc) -> RenameBlocksRequest:
    block = doc.Blocks.Item("OLD")
    member = block.members[0]
    return RenameBlocksRequest(
        document_id=doc.Name,
        definitions=(
            BlockDefinitionSnapshot(
                name="OLD",
                definition_revision="def-r1",
                base_point=Point3D(x=0, y=0),
                members=(
                    BlockMemberSnapshot(
                        handle=member.Handle,
                        owner_revision="def-r1",
                        entity_type="LINE",
                        geometry_digest=DIGEST_A,
                        layer="BLOCK",
                    ),
                ),
            ),
        ),
        copy_instead_of_rename=False,
        ignore_existing_name_collisions=False,
        exact_results=(
            RenameResult(
                source_name="OLD",
                source_revision="def-r1",
                result_name="NEW",
                result_revision="def-r2",
            ),
        ),
    )


def test_tx_rectangular_subset_mutates_text_and_creates_exact_boundary(doc: Doc) -> None:
    request = tx_request(doc)
    preview = live.preview_live_tx(request)
    wrapped = live.LiveTXExecuteRequest(
        request=request,
        expected_sources=tuple(
            live.LiveEntityEvidence.model_validate(item) for item in preview["expected_sources"]
        ),
        approval_fingerprint=preview["approval_fingerprint"],
    )
    result = live.execute_live_tx(wrapped)
    text = doc.entities["T1"]
    boundary = doc.entities[result.created_handles[0]]
    assert isinstance(text, Text) and text.TextString == "ROOM" and text.Height == 3
    assert isinstance(boundary, Polyline) and boundary.Closed and boundary.Layer == "ANNO"
    assert result.postcondition_verified and doc.marks == ["start", "end"]


def test_tx_rejects_stale_locked_and_semantic_expansion(doc: Doc) -> None:
    request = tx_request(doc)
    preview = live.preview_live_tx(request)
    doc.entities["T1"].TextString = "stale"  # type: ignore[attr-defined]
    wrapped = live.LiveTXExecuteRequest(
        request=request,
        expected_sources=tuple(
            live.LiveEntityEvidence.model_validate(item) for item in preview["expected_sources"]
        ),
        approval_fingerprint=preview["approval_fingerprint"],
    )
    with pytest.raises(ValueError, match="stale"):
        live.execute_live_tx(wrapped)
    doc.entities["T1"].TextString = "room"  # type: ignore[attr-defined]
    doc.Layers.Item("TEXT").Lock = True
    with pytest.raises(ValueError, match="locked"):
        live.preview_live_tx(request)
    doc.Layers.Item("TEXT").Lock = False
    with pytest.raises(ValueError, match="limited"):
        live.preview_live_tx(request.model_copy(update={"shape": TextBoxShape.CIRCLE}))


def test_tx_rejects_fingerprint_and_rolls_back_failed_postcondition(
    doc: Doc,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = tx_request(doc)
    preview = live.preview_live_tx(request)
    wrapped = live.LiveTXExecuteRequest(
        request=request,
        expected_sources=tuple(
            live.LiveEntityEvidence.model_validate(item) for item in preview["expected_sources"]
        ),
        approval_fingerprint="sha256:" + "0" * 64,
    )
    with pytest.raises(ValueError, match="fingerprint"):
        live.execute_live_tx(wrapped)

    output = Polyline("BAD", (-1.0, -1.0, 5.0, -1.0, 5.0, 3.0, -1.0, 3.0))
    output.Closed = False

    class IgnoreClosed:
        def __setattr__(self, name: str, value: Any) -> None:
            if name == "Closed":
                return
            setattr(output, name, value)

        def __getattr__(self, name: str) -> Any:
            return getattr(output, name)

    monkeypatch.setattr(live, "_lwpolyline", lambda _space, _vertices: IgnoreClosed())
    wrapped = wrapped.model_copy(
        update={"approval_fingerprint": preview["approval_fingerprint"]}
    )
    with pytest.raises(RuntimeError, match="postcondition"):
        live.execute_live_tx(wrapped)
    text = doc.entities["T1"]
    assert isinstance(text, Text)
    assert text.TextString == "room" and text.Height == 2.5
    assert output.deleted and doc.marks == ["start", "end"]


def test_brn_renames_static_definition_and_rolls_back_failure(doc: Doc) -> None:
    request = brn_request(doc)
    preview = live.preview_live_brn(request)
    wrapped = live.LiveBRNExecuteRequest(
        request=request,
        expected_sources=tuple(
            live.LiveBlockEvidence.model_validate(item) for item in preview["expected_sources"]
        ),
        approval_fingerprint=preview["approval_fingerprint"],
    )
    result = live.execute_live_brn(wrapped)
    assert doc.Blocks.Item("NEW").Name == "NEW"
    assert result.renamed_blocks == (("OLD", "NEW"),) and result.postcondition_verified

    rollback_doc = Doc()
    rollback_request = brn_request(rollback_doc)
    monkey = pytest.MonkeyPatch()
    monkey.setattr(live, "_drawing", lambda _name: rollback_doc)
    try:
        rollback_preview = live.preview_live_brn(rollback_request)
        rollback_doc.Blocks.Item("OLD").fail_rename = True
        with pytest.raises(RuntimeError, match="injected"):
            live.execute_live_brn(
                live.LiveBRNExecuteRequest(
                    request=rollback_request,
                    expected_sources=tuple(
                        live.LiveBlockEvidence.model_validate(item)
                        for item in rollback_preview["expected_sources"]
                    ),
                    approval_fingerprint=rollback_preview["approval_fingerprint"],
                )
            )
        assert rollback_doc.Blocks.Item("OLD").Name == "OLD"
        assert rollback_doc.marks == ["start", "end"]
    finally:
        monkey.undo()


def test_brn_rejects_collision_copy_locked_and_xref(doc: Doc) -> None:
    request = brn_request(doc)
    doc.Blocks.add("NEW", [Member("B2")])
    with pytest.raises(ValueError, match="already exists"):
        live.preview_live_brn(request)
    doc.Blocks.items.pop("new")
    with pytest.raises(ValueError, match="copy-and-rebind"):
        live.preview_live_brn(request.model_copy(update={"copy_instead_of_rename": True}))
    doc.Layers.Item("BLOCK").Lock = True
    with pytest.raises(ValueError, match="locked"):
        live.preview_live_brn(request)
    doc.Layers.Item("BLOCK").Lock = False
    doc.Blocks.Item("OLD").IsXRef = True
    with pytest.raises(ValueError, match="xref"):
        live.preview_live_brn(request)


def test_brn_rejects_fingerprint_and_stale_member_state(doc: Doc) -> None:
    request = brn_request(doc)
    preview = live.preview_live_brn(request)
    wrapped = live.LiveBRNExecuteRequest(
        request=request,
        expected_sources=tuple(
            live.LiveBlockEvidence.model_validate(item) for item in preview["expected_sources"]
        ),
        approval_fingerprint="sha256:" + "0" * 64,
    )
    with pytest.raises(ValueError, match="fingerprint"):
        live.execute_live_brn(wrapped)
    member = doc.Blocks.Item("OLD").members[0]
    member.StartPoint = (9.0, 9.0, 0.0)
    wrapped = wrapped.model_copy(
        update={"approval_fingerprint": preview["approval_fingerprint"]}
    )
    with pytest.raises(ValueError, match="no longer matches"):
        live.execute_live_brn(wrapped)


def test_registers_three_preview_execute_pairs() -> None:
    class MCP:
        def __init__(self) -> None:
            self.names: list[str] = []

        def tool(self, *, name: str, annotations: Any) -> Any:
            del annotations
            self.names.append(name)
            return lambda function: function

    mcp = MCP()
    live.register_live_gap_25_32_tools(mcp)  # type: ignore[arg-type]
    assert mcp.names == [
        "xicad_preview_live_tx",
        "xicad_execute_live_tx",
        "xicad_preview_live_brn",
        "xicad_execute_live_brn",
    ]
    assert "postcondition verification is unavailable" in live.BLOCKED["MK"]
