from __future__ import annotations

from types import SimpleNamespace

from src.adapters.zwcad_com_adapter import ZWCADCOMAdapter


class FakeConsolidationAdapter(ZWCADCOMAdapter):
    def __init__(self, objects):
        super().__init__()
        self.objects = objects
        self.created_layers: list[str] = []
        self.regenerated = False

    def _iter_modelspace(self):
        yield from self.objects

    def _ensure_layer(self, layer: str) -> None:
        self.created_layers.append(layer)

    def _regen(self) -> None:
        self.regenerated = True


def test_consolidate_other_layers_dry_run_preserves_user_standard_layers() -> None:
    objects = [
        SimpleNamespace(Handle="1", Layer="COL"),
        SimpleNamespace(Handle="2", Layer="WAL7"),
        SimpleNamespace(Handle="3", Layer="RANDOM-A"),
        SimpleNamespace(Handle="4", Layer="TITLE-OLD"),
        SimpleNamespace(Handle="5", Layer="DEFPOINTS"),
        SimpleNamespace(Handle="6", Layer="HAT"),
        SimpleNamespace(Handle="7", Layer="HID2"),
        SimpleNamespace(Handle="8", Layer="SYM_TEXT"),
        SimpleNamespace(Handle="9", Layer="ELE2"),
    ]
    adapter = FakeConsolidationAdapter(objects)

    result = adapter.consolidate_other_layers(target_layer="ETC", keep_layers=["TITLE-OLD"], dry_run=True)

    assert result["changed"] == 3
    assert result["source_layers"] == {"RANDOM-A": 1}
    assert result["review_layers"] == {"RANDOM-A": 1}
    assert result["mapped_layers"] == {"HID2 -> HID": 1, "SYM_TEXT -> SYM": 1}
    assert objects[2].Layer == "RANDOM-A"
    assert adapter.created_layers == []


def test_consolidate_other_layers_execute_moves_only_unknown_layers() -> None:
    objects = [
        SimpleNamespace(Handle="1", Layer="COL"),
        SimpleNamespace(Handle="2", Layer="UNKNOWN_LAYER"),
        SimpleNamespace(Handle="3", Layer="ETC"),
    ]
    adapter = FakeConsolidationAdapter(objects)

    result = adapter.consolidate_other_layers(target_layer="ETC", dry_run=False)

    assert result["changed"] == 1
    assert result["source_layers"] == {"UNKNOWN_LAYER": 1}
    assert objects[0].Layer == "COL"
    assert objects[1].Layer == "ETC"
    assert objects[2].Layer == "ETC"
    assert adapter.created_layers == ["ETC"]
    assert adapter.regenerated is True


def test_consolidate_other_layers_maps_known_aliases_to_standard_layers() -> None:
    objects = [
        SimpleNamespace(Handle="1", Layer="부호도"),
        SimpleNamespace(Handle="2", Layer="해치선"),
        SimpleNamespace(Handle="3", Layer="조적"),
    ]
    adapter = FakeConsolidationAdapter(objects)

    result = adapter.consolidate_other_layers(target_layer="ETC", dry_run=False)

    assert result["changed"] == 3
    assert result["mapped_layers"] == {"부호도 -> SYM": 1, "해치선 -> HAT": 1, "조적 -> WAL2": 1}
    assert [obj.Layer for obj in objects] == ["SYM", "HAT", "WAL2"]
