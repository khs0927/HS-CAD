from __future__ import annotations

from typing import Any

import pytest

from xicad_mcp.headless_core_batch1 import Point3D
from xicad_mcp.headless_core_batch7 import (
    SequentialEdit,
    SequentialEditRequest,
    SourceDisposition,
    SplitMode,
    StackAnchor,
    StackDirection,
    StyleScope,
    TextSplitRequest,
    TextStackRequest,
    TextStyleRequest,
    TextSwapRequest,
    TextWidthRequest,
)
from xicad_mcp.live_text_batch7b import (
    LiveTseExecuteRequest,
    LiveTsoExecuteRequest,
    LiveTspExecuteRequest,
    LiveTstExecuteRequest,
    LiveTswExecuteRequest,
    LiveTwExecuteRequest,
    execute_live_tse,
    execute_live_tso,
    execute_live_tsp,
    execute_live_tst,
    execute_live_tsw,
    execute_live_tw,
    preview_live_tse,
    preview_live_tso,
    preview_live_tsp,
    preview_live_tst,
    preview_live_tsw,
    preview_live_tw,
)


class FakeLayer:
    Lock = False


class FakeCollection:
    def __init__(self, names: tuple[str, ...]) -> None:
        self.names = {name.casefold(): FakeLayer() for name in names}

    def Item(self, name: str) -> Any:
        try:
            return self.names[name.casefold()]
        except KeyError as exc:
            raise RuntimeError(name) from exc


class FakeText:
    def __init__(self, block: FakeBlock, handle: str, text: str, x: float) -> None:
        self.block = block
        self.Handle = handle
        self.ObjectName = "AcDbText"
        self.TextString = text
        self.Layer = "TEXT"
        self.StyleName = "Standard"
        self.Height = 2.5
        self.InsertionPoint = (x, 0.0, 0.0)
        self.Rotation = 0.0
        self.ScaleFactor = 1.0

    def Delete(self) -> None:
        self.block.entities.remove(self)


class FakeBlock:
    def __init__(self, name: str) -> None:
        self.Name = name
        self.IsLayout = True
        self.entities: list[FakeText] = []

    def add(self, handle: str, text: str, x: float = 0.0) -> FakeText:
        entity = FakeText(self, handle, text, x)
        self.entities.append(entity)
        return entity

    def AddText(self, text: str, point: tuple[float, float, float], height: float) -> FakeText:
        entity = self.add(f"N{len(self.entities)}", text, point[0])
        entity.InsertionPoint = point
        entity.Height = height
        return entity

    def __iter__(self):
        return iter(self.entities.copy())


class FakeDocument:
    def __init__(self) -> None:
        self.Name = "Drawing1.dwg"
        model = FakeBlock("*Model_Space")
        model.add("A", "one", 1)
        model.add("B", "two", 2)
        self.Blocks = [model]
        self.ModelSpace = model
        self.Layers = FakeCollection(("TEXT",))
        self.TextStyles = FakeCollection(("Standard", "NewStyle"))
        self.events: list[str] = []

    def StartUndoMark(self) -> None:
        self.events.append("start")

    def EndUndoMark(self) -> None:
        self.events.append("end")


def execute_model(model: type[Any], preview: dict[str, Any]) -> Any:
    values = {
        "request": preview["request"],
        "expected_entities": preview["expected_entities"],
        "approval_fingerprint": preview["approval_fingerprint"],
    }
    if model is LiveTwExecuteRequest:
        values["expected_width_factors"] = preview["expected_width_factors"]
    return model(**values)


@pytest.fixture
def doc(monkeypatch: pytest.MonkeyPatch) -> FakeDocument:
    value = FakeDocument()
    monkeypatch.setattr("xicad_mcp.live_text_batch7b._drawing", lambda _name: value)
    monkeypatch.setattr(
        "xicad_mcp.live_text_batch7b._variant_point",
        lambda point: (point.x, point.y, point.z),
    )
    return value


def test_tse_exact_text_edit(doc: FakeDocument) -> None:
    request = SequentialEditRequest(
        document_id=doc.Name,
        edits=(SequentialEdit(handle="A", expected_text="one", replacement_text="ONE"),),
    )
    result = execute_live_tse(execute_model(LiveTseExecuteRequest, preview_live_tse(request)))
    assert doc.ModelSpace.entities[0].TextString == "ONE"
    assert result.changed_handles == ("A",)
    assert doc.events == ["start", "end"]


def test_tso_moves_in_explicit_order(doc: FakeDocument) -> None:
    request = TextStackRequest(
        document_id=doc.Name,
        target_handles=("A", "B"),
        direction=StackDirection.VERTICAL,
        gap=10,
        anchor=StackAnchor.EXPLICIT,
        anchor_point=Point3D(x=5, y=20),
        order=("B", "A"),
    )
    result = execute_live_tso(execute_model(LiveTsoExecuteRequest, preview_live_tso(request)))
    assert doc.ModelSpace.entities[1].InsertionPoint == (5.0, 20.0, 0.0)
    assert doc.ModelSpace.entities[0].InsertionPoint == (5.0, 10.0, 0.0)
    assert result.postcondition_verified


def test_tsp_creates_pieces_and_replaces_source(doc: FakeDocument) -> None:
    doc.ModelSpace.entities[0].TextString = "A/B/C"
    request = TextSplitRequest(
        document_id=doc.Name,
        target_handles=("A",),
        mode=SplitMode.DELIMITER,
        delimiter="/",
        source_disposition=SourceDisposition.REPLACE,
        offset=Point3D(x=10, y=0),
    )
    result = execute_live_tsp(execute_model(LiveTspExecuteRequest, preview_live_tsp(request)))
    assert [item.TextString for item in doc.ModelSpace.entities if item.Handle.startswith("N")] == ["A", "B", "C"]
    assert result.erased_handles == ("A",)
    assert len(result.created_handles) == 3


def test_tst_changes_only_selected_styles(doc: FakeDocument) -> None:
    request = TextStyleRequest(
        document_id=doc.Name,
        target_style="NewStyle",
        scope=StyleScope.SELECTED,
        target_handles=("A",),
    )
    result = execute_live_tst(execute_model(LiveTstExecuteRequest, preview_live_tst(request)))
    assert doc.ModelSpace.entities[0].StyleName == "NewStyle"
    assert doc.ModelSpace.entities[1].StyleName == "Standard"
    assert result.command_alias == "TST"


def test_tsw_swaps_content_only(doc: FakeDocument) -> None:
    request = TextSwapRequest(document_id=doc.Name, first_handle="A", second_handle="B")
    result = execute_live_tsw(execute_model(LiveTswExecuteRequest, preview_live_tsw(request)))
    assert [item.TextString for item in doc.ModelSpace.entities] == ["two", "one"]
    assert result.changed_handles == ("A", "B")


def test_tw_fingerprints_existing_width_and_changes_factor(doc: FakeDocument) -> None:
    request = TextWidthRequest(document_id=doc.Name, target_handles=("A", "B"), width_factor=0.8)
    preview = preview_live_tw(request)
    assert preview["expected_width_factors"] == (1.0, 1.0)
    result = execute_live_tw(execute_model(LiveTwExecuteRequest, preview))
    assert [item.ScaleFactor for item in doc.ModelSpace.entities] == [0.8, 0.8]
    assert result.postcondition_verified


def test_entity_drift_is_rejected_before_undo(doc: FakeDocument) -> None:
    request = TextSwapRequest(document_id=doc.Name, first_handle="A", second_handle="B")
    execution = execute_model(LiveTswExecuteRequest, preview_live_tsw(request))
    doc.ModelSpace.entities[0].TextString = "changed"
    with pytest.raises(ValueError, match="no longer matches"):
        execute_live_tsw(execution)
    assert doc.events == []


def test_tampered_fingerprint_is_rejected_before_cad(monkeypatch: pytest.MonkeyPatch) -> None:
    request = LiveTswExecuteRequest(
        request=TextSwapRequest(document_id="Drawing1.dwg", first_handle="A", second_handle="B"),
        expected_entities=(),
        approval_fingerprint="sha256:" + "0" * 64,
    )
    monkeypatch.setattr(
        "xicad_mcp.live_text_batch7b._drawing",
        lambda _name: pytest.fail("CAD must not be contacted"),
    )
    with pytest.raises(ValueError, match="fingerprint"):
        execute_live_tsw(request)
