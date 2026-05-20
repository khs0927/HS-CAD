from src.adapters.zwcad_com_adapter import ZWCADCOMAdapter


def test_adapter_import_and_methods_exist():
    adapter = ZWCADCOMAdapter(visible=False)
    for name in [
        'run_command',
        'load_lisp',
        'replace_block',
        'delete_layer_objects',
        'create_line',
        'create_polyline',
        'insert_block',
        'configure_drawing_standards',
        'create_aligned_dimension',
        'create_orthogonal_leader',
        'apply_batting_linetype',
    ]:
        assert hasattr(adapter, name)
