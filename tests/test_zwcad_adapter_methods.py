from src.adapters.zwcad_com_adapter import ZWCADCOMAdapter


def test_adapter_import_and_methods_exist():
    adapter = ZWCADCOMAdapter(visible=False)
    for name in ['run_command', 'load_lisp', 'replace_block', 'delete_layer_objects', 'create_line', 'create_polyline', 'insert_block']:
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
