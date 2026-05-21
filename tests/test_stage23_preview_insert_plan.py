from src.neuro_seq_cad_bridge.preview_insert import insert_dxf_preview


def test_insert_preview_dry_run_does_not_connect():
    plan = {"can_execute": True, "source_dxf": "missing.dxf", "warnings": []}
    result = insert_dxf_preview(None, plan, allow_execute=False)
    assert result["executed"] is False
    assert result["saved"] is False
    assert result["warnings"]
