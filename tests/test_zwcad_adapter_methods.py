from src.adapters.zwcad_com_adapter import ZWCADCOMAdapter


def test_adapter_import_and_methods_exist():
    adapter = ZWCADCOMAdapter(visible=False)
    for name in ['run_command', 'load_lisp', 'replace_block', 'delete_layer_objects', 'create_line', 'create_polyline', 'insert_block', 'get_entity_by_handle']:
        assert hasattr(adapter, name)


class _FakeObj:
    Handle = 'A1'
    ObjectName = 'AcDbText'
    Layer = 'TEXT'
    TextString = 'Hello world'
    InsertionPoint = (1.0, 2.0, 0.0)
    Height = 100.0
    Rotation = 0.0


def test_scan_readers_minimal_and_index_shapes():
    adapter = ZWCADCOMAdapter(visible=False)
    minimal = adapter._entity_to_dict_minimal(_FakeObj())
    indexed = adapter._entity_to_dict_index(_FakeObj())

    assert minimal == {
        'handle': 'A1',
        'object_name': 'AcDbText',
        'entity_type': 'TEXT',
        'layer': 'TEXT',
    }
    assert indexed['text'] == 'Hello world'
    assert indexed['bbox'] == [1.0, 2.0, 1.0, 2.0]
