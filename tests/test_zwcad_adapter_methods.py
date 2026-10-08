from src.adapters.zwcad_com_adapter import ZWCADCOMAdapter


def test_adapter_import_and_methods_exist():
    adapter = ZWCADCOMAdapter(visible=False)
    for name in ['run_command', 'load_lisp', 'replace_block', 'delete_layer_objects', 'create_line', 'create_polyline', 'insert_block', 'list_texts']:
        assert hasattr(adapter, name)


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
