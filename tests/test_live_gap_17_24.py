from __future__ import annotations

import pytest

from xicad_mcp.headless_core_batch18 import TableWidthRequest
from xicad_mcp.live_gap_17_24 import (
    LiveTajExecuteRequest,
    LiveTajPreviewRequest,
    _fingerprint,
    execute_live_taj,
    preview_live_taj,
)


class FakeLayer:
    def __init__(self, name: str, *, locked: bool = False) -> None:
        self.Name = name
        self.Lock = locked


class FakeLayers:
    def __init__(self, layers: dict[str, FakeLayer]) -> None:
        self.layers = layers

    def Item(self, name: str) -> FakeLayer:
        return self.layers[name]


class FakeTable:
    ObjectName = "AcDbTable"

    def __init__(
        self,
        handle: str = "T1",
        *,
        layer: str = "TABLE",
        cells: tuple[tuple[str, ...], ...] = (("ROOM", "AREA"), ("LIVING", "24.0")),
        widths: tuple[float, ...] = (5.0, 5.0),
        text_height: float = 2.0,
    ) -> None:
        self.Handle = handle
        self.Layer = layer
        self.Rows = len(cells)
        self.Columns = len(cells[0])
        self.cells = cells
        self.widths = list(widths)
        self.text_height = text_height
        self.fail_column: int | None = None
        self.update_count = 0

    def GetText(self, row: int, column: int) -> str:
        return self.cells[row][column]

    def GetColumnWidth(self, column: int) -> float:
        return self.widths[column]

    def SetColumnWidth(self, column: int, width: float) -> None:
        if self.fail_column == column:
            self.fail_column = None
            raise RuntimeError("synthetic width failure")
        self.widths[column] = width

    def GetCellTextHeight(self, row: int, column: int) -> float:
        del row, column
        return self.text_height

    def Update(self) -> None:
        self.update_count += 1


class FakeBlock(list):
    IsLayout = True


class FakeDocument:
    Name = "Drawing1.dwg"

    def __init__(self, *tables: FakeTable, locked: bool = False) -> None:
        self.Blocks = [FakeBlock(tables)]
        self.Layers = FakeLayers({table.Layer: FakeLayer(table.Layer, locked=locked) for table in tables})
        self.open_marks = 0
        self.closed_marks = 0
        self.activated = 0

    def Activate(self) -> None:
        self.activated += 1

    def StartUndoMark(self) -> None:
        self.open_marks += 1

    def EndUndoMark(self) -> None:
        self.closed_marks += 1


def _request() -> TableWidthRequest:
    return TableWidthRequest(
        document_id="Drawing1.dwg",
        table_handles=("T1",),
        character_width_factor=0.6,
        horizontal_padding=1.0,
        minimum_width=3.0,
    )


def _approved(monkeypatch: pytest.MonkeyPatch, table: FakeTable | None = None):
    from xicad_mcp import live_gap_17_24

    table = table or FakeTable()
    doc = FakeDocument(table)
    monkeypatch.setattr(live_gap_17_24, "_drawing", lambda _name: doc)
    preview = preview_live_taj(LiveTajPreviewRequest(document_name="Drawing1.dwg", request=_request()))
    execute = LiveTajExecuteRequest(
        document_name="Drawing1.dwg",
        request=_request(),
        expected_tables=preview["expected_tables"],
        approval_fingerprint=preview["approval_fingerprint"],
    )
    return table, doc, preview, execute


def test_preview_binds_full_table_state_and_official_evidence(monkeypatch: pytest.MonkeyPatch) -> None:
    table, _doc, preview, _execute = _approved(monkeypatch)

    assert preview["command_alias"] == "TAJ"
    assert preview["live_executable"] is True
    assert preview["expected_tables"][0]["cells"] == [list(row) for row in table.cells]
    assert preview["expected_tables"][0]["column_widths"] == table.widths
    assert preview["semantic_evidence"]["xicad_help"] == "https://izzarder.com/305"
    payload = {
        key: value
        for key, value in preview.items()
        if key not in {"approval_fingerprint", "mutation", "live_executable", "scope_note"}
    }
    assert preview["approval_fingerprint"] == _fingerprint(payload)


def test_execute_sets_each_width_and_verifies_text_unchanged(monkeypatch: pytest.MonkeyPatch) -> None:
    table, doc, _preview, execute = _approved(monkeypatch)

    result = execute_live_taj(execute)

    # max text lengths are 6 and 4; width = len * 2.0 * 0.6 + 2 * 1.0
    assert table.widths == pytest.approx([9.2, 6.8])
    assert table.cells == (("ROOM", "AREA"), ("LIVING", "24.0"))
    assert result.command_alias == "TAJ"
    assert result.changed_handles == ("T1",)
    assert result.postcondition_verified is True
    assert result.rollback_performed is False
    assert doc.open_marks == doc.closed_marks == 1


def test_execute_rejects_stale_table_before_undo_mark(monkeypatch: pytest.MonkeyPatch) -> None:
    table, doc, _preview, execute = _approved(monkeypatch)
    table.cells = (("ROOM", "AREA"), ("CHANGED", "24.0"))

    with pytest.raises(ValueError, match="stale"):
        execute_live_taj(execute)

    assert table.widths == [5.0, 5.0]
    assert doc.open_marks == doc.closed_marks == 0


def test_execute_rejects_fingerprint_tampering(monkeypatch: pytest.MonkeyPatch) -> None:
    _table, doc, _preview, execute = _approved(monkeypatch)
    tampered = execute.model_copy(update={"approval_fingerprint": "sha256:" + "0" * 64})

    with pytest.raises(ValueError, match="fingerprint"):
        execute_live_taj(tampered)

    assert doc.open_marks == doc.closed_marks == 0


def test_execute_rolls_back_partial_com_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    table, doc, _preview, execute = _approved(monkeypatch)
    table.fail_column = 1

    with pytest.raises(RuntimeError, match="synthetic"):
        execute_live_taj(execute)

    assert table.widths == [5.0, 5.0]
    assert doc.open_marks == doc.closed_marks == 1


@pytest.mark.parametrize(
    ("layer", "locked", "message"),
    [
        ("TABLE", True, "locked or xref"),
        ("XREF|TABLE", False, "locked or xref"),
    ],
)
def test_preview_rejects_locked_and_xref_tables(
    monkeypatch: pytest.MonkeyPatch,
    layer: str,
    locked: bool,
    message: str,
) -> None:
    from xicad_mcp import live_gap_17_24

    table = FakeTable(layer=layer)
    doc = FakeDocument(table, locked=locked)
    monkeypatch.setattr(live_gap_17_24, "_drawing", lambda _name: doc)

    with pytest.raises(ValueError, match=message):
        preview_live_taj(LiveTajPreviewRequest(document_name="Drawing1.dwg", request=_request()))


def test_preview_uses_largest_mixed_text_height(monkeypatch: pytest.MonkeyPatch) -> None:
    from xicad_mcp import live_gap_17_24

    table = FakeTable()
    table.GetCellTextHeight = lambda row, column: 2.0 if (row, column) == (0, 0) else 3.0
    doc = FakeDocument(table)
    monkeypatch.setattr(live_gap_17_24, "_drawing", lambda _name: doc)

    preview = preview_live_taj(LiveTajPreviewRequest(document_name="Drawing1.dwg", request=_request()))

    assert preview["expected_tables"][0]["text_height"] == 3.0
