from __future__ import annotations

from types import SimpleNamespace

from src.ui.zwcad_autocomplete_ui import ZWCADAutocompletePanel


class _Label:
    def __init__(self) -> None:
        self.text = ""
        self.style = ""

    def setText(self, value: str) -> None:
        self.text = value

    def setStyleSheet(self, value: str) -> None:
        self.style = value


def test_connect_to_zwcad_uses_adapter_app_state() -> None:
    class Adapter:
        app = None

        def connect(self) -> None:
            self.app = object()

    panel = SimpleNamespace(zwcad_adapter=Adapter(), status_label=_Label(), is_connected=False)

    ZWCADAutocompletePanel.connect_to_zwcad(panel)

    assert panel.is_connected is True
    assert "정상적으로 연결" in panel.status_label.text


def test_insert_selected_assigns_existing_note_layer(monkeypatch) -> None:
    class Layers:
        def Add(self, _name: str) -> None:
            raise RuntimeError("layer already exists")

    class MText:
        Height = 0.0
        Layer = "0"

    mtext = MText()
    model_space = SimpleNamespace(AddMText=lambda *_args: mtext)
    utility = SimpleNamespace(GetPoint=lambda **_kwargs: [0.0, 0.0, 0.0])
    document = SimpleNamespace(
        Utility=utility,
        ModelSpace=model_space,
        Layers=Layers(),
        GetVariable=lambda _name: 3.0,
        Regen=lambda _mode: None,
    )
    adapter = SimpleNamespace(app=SimpleNamespace(ActiveDocument=document))
    selected = SimpleNamespace(text=lambda: "테스트 지시선")
    panel = SimpleNamespace(
        list_widget=SimpleNamespace(selectedItems=lambda: [selected]),
        zwcad_adapter=adapter,
        is_connected=True,
        connect_to_zwcad=lambda: None,
        status_label=_Label(),
    )
    monkeypatch.setattr("src.ui.zwcad_autocomplete_ui.QApplication.processEvents", lambda: None)

    ZWCADAutocompletePanel.insert_selected_to_cad(panel)

    assert mtext.Layer == "HS-CAD-ADD-NOTE"
