import types

from src.adapters.zwcad_com_adapter import ZWCADCOMAdapter


def test_adapter_import_and_methods_exist():
    adapter = ZWCADCOMAdapter(visible=False)
    for name in ['run_command', 'load_lisp', 'replace_block', 'delete_layer_objects', 'create_line', 'create_polyline', 'insert_block', 'list_texts']:
        assert hasattr(adapter, name)


def test_adapter_accepts_version_pin_and_orders_progids():
    adapter = ZWCADCOMAdapter(visible=False, version="2026", start_if_needed=False)
    assert adapter.version == "2026"
    assert adapter.start_if_needed is False
    assert adapter.active_progid is None
    assert adapter._candidate_progids() == (
        "ZWCAD.Application.2026",
        "ZWCAD.Application",
    )


def test_list_texts_filters_modelspace_scan(monkeypatch):
    adapter = ZWCADCOMAdapter(visible=False)
    monkeypatch.setattr(
        adapter,
        'scan_modelspace',
        lambda: [
            {'type': 'TEXT', 'text': 'Room'},
            {'type': 'LINE'},
            {'type': 'MTEXT', 'text': 'Notes'},
            {'type': 'TEXT', 'text': None},
        ],
    )

    assert adapter.list_texts() == ['Room', 'Notes']


def test_scan_modelspace_returns_rich_entities_and_list_texts_uses_them(monkeypatch):
    line = types.SimpleNamespace(ObjectName="AcDbLine", Handle="1A", Layer="A-WALL", StartPoint=(0.0, 0.0, 0.0), EndPoint=(10.0, 0.0, 0.0), Length=10.0)
    text = types.SimpleNamespace(ObjectName="AcDbText", Handle="1B", Layer="A-ANNO", InsertionPoint=(1.0, 2.0, 0.0), TextString="거실", Height=150.0)
    doc = types.SimpleNamespace(ModelSpace=[line, text])
    adapter = ZWCADCOMAdapter(visible=False)
    monkeypatch.setattr(adapter, "get_active_document", lambda: doc)

    rows = adapter.scan_modelspace()

    assert [r["entity_type"] for r in rows] == ["LINE", "TEXT"]
    assert rows[0]["start"] == [0.0, 0.0, 0.0] and rows[0]["layer"] == "A-WALL"
    assert rows[1]["handle"] == "1B" and rows[1]["insert"] == [1.0, 2.0, 0.0]
    assert adapter.list_texts() == ["거실"]
