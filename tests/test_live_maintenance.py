from __future__ import annotations

from typing import Any

import pytest

from xicad_mcp.live_maintenance import (
    LiveApdExecuteRequest,
    LiveApdPreviewRequest,
    LiveLayerFilterCommand,
    LiveLayerFilterExecuteRequest,
    LiveLayerFilterPreviewRequest,
    execute_live_apd,
    execute_live_lfd,
    execute_live_lpd,
    preview_live_apd,
    preview_live_layer_filter_delete,
)
from xicad_mcp.maintenance_cores import DrawingSpace


class FakeEntity:
    def __init__(self, block: FakeBlock, handle: str, object_name: str) -> None:
        self.block = block
        self.Handle = handle
        self.ObjectName = object_name

    def Delete(self) -> None:
        self.block.entities.remove(self)


class FakeBlock:
    def __init__(self, name: str, is_layout: bool = True) -> None:
        self.Name = name
        self.IsLayout = is_layout
        self.entities: list[FakeEntity] = []

    def add(self, handle: str, object_name: str) -> FakeEntity:
        entity = FakeEntity(self, handle, object_name)
        self.entities.append(entity)
        return entity

    def __iter__(self):
        return iter(self.entities.copy())


class FakeFilter:
    def __init__(self, dictionary: FakeDictionary, name: str) -> None:
        self.dictionary = dictionary
        self.name = name

    def Delete(self) -> None:
        self.dictionary.items.remove(self)


class FakeDictionary:
    def __init__(self, names: tuple[str, ...]) -> None:
        self.items: list[FakeFilter] = []
        self.items.extend(FakeFilter(self, name) for name in names)

    @property
    def Count(self) -> int:
        return len(self.items)

    def Item(self, key: int | str) -> FakeFilter:
        if isinstance(key, int):
            return self.items[key]
        return next(item for item in self.items if item.name.casefold() == key.casefold())

    def GetName(self, item: FakeFilter) -> str:
        return item.name


class FakeDictionaries:
    def __init__(self, filters: FakeDictionary | None) -> None:
        self.filters = filters

    def Item(self, name: str) -> FakeDictionary:
        if self.filters is None or name != "ACAD_LAYERFILTERS":
            raise KeyError(name)
        return self.filters


class FakeDocument:
    def __init__(self, filter_names: tuple[str, ...] = ()) -> None:
        self.Name = "Drawing1.dwg"
        model = FakeBlock("*Model_Space")
        paper = FakeBlock("*Paper_Space")
        definitions = FakeBlock("Door", is_layout=False)
        model.add("A", "AcDbPoint")
        model.add("B", "AcDbLine")
        paper.add("C", "AcDbPoint")
        definitions.add("D", "AcDbPoint")
        self.Blocks = [model, paper, definitions]
        self.filter_dictionary = FakeDictionary(filter_names) if filter_names else None
        self.Dictionaries = FakeDictionaries(self.filter_dictionary)
        self.events: list[str] = []

    def StartUndoMark(self) -> None:
        self.events.append("start")

    def EndUndoMark(self) -> None:
        self.events.append("end")


def approved_apd(preview: dict[str, Any]) -> LiveApdExecuteRequest:
    return LiveApdExecuteRequest(
        document_name=preview["document_name"],
        spaces=preview["spaces"],
        expected_entities=preview["expected_entities"],
        approval_fingerprint=preview["approval_fingerprint"],
    )


def approved_filters(preview: dict[str, Any]) -> LiveLayerFilterExecuteRequest:
    return LiveLayerFilterExecuteRequest(
        document_name=preview["document_name"],
        command_alias=preview["command_alias"],
        delete_all_user_filters=preview["delete_all_user_filters"],
        include_names=preview["include_names"],
        preserve_names=preview["preserve_names"],
        expected_filter_names=preview["expected_filter_names"],
        expected_selected_names=preview["expected_selected_names"],
        approval_fingerprint=preview["approval_fingerprint"],
    )


def test_apd_preview_finds_points_only_in_requested_layout_spaces(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    doc = FakeDocument()
    monkeypatch.setattr("xicad_mcp.live_maintenance._drawing", lambda _name: doc)
    result = preview_live_apd(LiveApdPreviewRequest(document_name=doc.Name))

    assert [item["handle"] for item in result["expected_entities"]] == ["A", "C"]
    assert result["approval_fingerprint"].startswith("sha256:")


def test_apd_executes_with_undo_and_verifies_deletion(monkeypatch: pytest.MonkeyPatch) -> None:
    doc = FakeDocument()
    monkeypatch.setattr("xicad_mcp.live_maintenance._drawing", lambda _name: doc)
    execution = approved_apd(preview_live_apd(LiveApdPreviewRequest(document_name=doc.Name)))

    result = execute_live_apd(execution)

    assert result.deleted_handles == ("A", "C")
    assert result.postcondition_verified is True
    assert doc.events == ["start", "end"]


def test_apd_rejects_inventory_drift_before_undo(monkeypatch: pytest.MonkeyPatch) -> None:
    doc = FakeDocument()
    monkeypatch.setattr("xicad_mcp.live_maintenance._drawing", lambda _name: doc)
    execution = approved_apd(preview_live_apd(LiveApdPreviewRequest(document_name=doc.Name)))
    doc.Blocks[0].add("E", "AcDbPoint")

    with pytest.raises(ValueError, match="inventory"):
        execute_live_apd(execution)
    assert doc.events == []


def test_apd_model_only_does_not_delete_paper_point(monkeypatch: pytest.MonkeyPatch) -> None:
    doc = FakeDocument()
    monkeypatch.setattr("xicad_mcp.live_maintenance._drawing", lambda _name: doc)
    preview = preview_live_apd(
        LiveApdPreviewRequest(document_name=doc.Name, spaces=(DrawingSpace.MODEL,))
    )

    result = execute_live_apd(approved_apd(preview))

    assert result.deleted_handles == ("A",)
    assert any(entity.Handle == "C" for entity in doc.Blocks[1])


@pytest.mark.parametrize("alias", [LiveLayerFilterCommand.LFD, LiveLayerFilterCommand.LPD])
def test_layer_filter_aliases_delete_selected_filters(
    monkeypatch: pytest.MonkeyPatch,
    alias: LiveLayerFilterCommand,
) -> None:
    doc = FakeDocument(("Architectural", "Keep", "Mechanical"))
    monkeypatch.setattr("xicad_mcp.live_maintenance._drawing", lambda _name: doc)
    request = LiveLayerFilterPreviewRequest(
        document_name=doc.Name,
        command_alias=alias,
        preserve_names=("Keep",),
    )
    execution = approved_filters(preview_live_layer_filter_delete(request))

    result = execute_live_lfd(execution) if alias is LiveLayerFilterCommand.LFD else execute_live_lpd(execution)

    assert result.deleted_names == ("Architectural", "Mechanical")
    assert [item.name for item in doc.filter_dictionary.items] == ["Keep"]
    assert all(item.absent for item in result.evidence)
    assert doc.events == ["start", "end"]


def test_specific_filter_mode_uses_existing_contract_validation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    doc = FakeDocument(("Architectural",))
    monkeypatch.setattr("xicad_mcp.live_maintenance._drawing", lambda _name: doc)
    request = LiveLayerFilterPreviewRequest(
        document_name=doc.Name,
        command_alias=LiveLayerFilterCommand.LFD,
        delete_all_user_filters=False,
    )
    with pytest.raises(ValueError, match="requires include_names"):
        preview_live_layer_filter_delete(request)


def test_filter_inventory_drift_is_rejected_before_undo(monkeypatch: pytest.MonkeyPatch) -> None:
    doc = FakeDocument(("Architectural",))
    monkeypatch.setattr("xicad_mcp.live_maintenance._drawing", lambda _name: doc)
    request = LiveLayerFilterPreviewRequest(
        document_name=doc.Name,
        command_alias=LiveLayerFilterCommand.LFD,
    )
    execution = approved_filters(preview_live_layer_filter_delete(request))
    doc.filter_dictionary.items.append(FakeFilter(doc.filter_dictionary, "NewFilter"))

    with pytest.raises(ValueError, match="inventory"):
        execute_live_lfd(execution)
    assert doc.events == []


def test_wrong_filter_alias_and_bad_fingerprint_are_rejected_before_cad(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = LiveLayerFilterExecuteRequest(
        document_name="Drawing1.dwg",
        command_alias=LiveLayerFilterCommand.LFD,
        expected_filter_names=(),
        expected_selected_names=(),
        approval_fingerprint="sha256:" + "0" * 64,
    )
    monkeypatch.setattr(
        "xicad_mcp.live_maintenance._drawing",
        lambda _name: pytest.fail("CAD must not be contacted"),
    )

    with pytest.raises(ValueError, match="only executes LPD"):
        execute_live_lpd(request)
    with pytest.raises(ValueError, match="fingerprint"):
        execute_live_lfd(request)
