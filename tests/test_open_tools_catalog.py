from src.integrations.tool_catalog import load_tool_catalog


def test_tool_catalog_has_core_entries():
    payload = load_tool_catalog()
    names = {item['name'] for item in payload['tools']}
    assert 'ezdxf' in names
    assert 'XiCAD' in names
