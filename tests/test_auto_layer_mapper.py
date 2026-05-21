from image_to_cad.auto.auto_layer_mapper import guess_layer_mapping


def test_auto_layer_mapper_common_aliases():
    assert guess_layer_mapping("003_COL").target_layer == "COL"
    assert guess_layer_mapping("S-STEEL BEAM").target_layer == "COL"
    assert guess_layer_mapping("WAL").target_layer == "WAL1"
    assert guess_layer_mapping("\uc870\uc801").target_layer == "WAL2"
    assert guess_layer_mapping("HA").target_layer == "HAT"
    assert guess_layer_mapping("\ubb38\uc790").target_layer == "TXT"
    assert guess_layer_mapping("DOOR1").target_layer == "DOOR"
    assert guess_layer_mapping("WINBAR").target_layer == "WINBAR"
    assert guess_layer_mapping("FIX-CUBICLE").target_layer == "FIX"
    assert guess_layer_mapping("INSUL").target_layer == "INS"
    assert guess_layer_mapping("@INS").target_layer == "INS"
    assert guess_layer_mapping("FORM").target_layer == "A-FORM"
    assert guess_layer_mapping("PAPER").target_layer == "A-FORM"
    assert guess_layer_mapping("TITLE").target_layer == "TIT"
    assert guess_layer_mapping("STAIR-IN").target_layer == "STAIR"
    assert guess_layer_mapping("GRID").target_layer == "GRID"
    assert guess_layer_mapping("unknown").target_layer is None


def test_layer_zero_default_blocked_but_optionally_allowed():
    blocked = guess_layer_mapping("0")
    assert blocked.target_layer is None
    assert blocked.blocked_reason == "protected_layer"
    allowed = guess_layer_mapping("0", allow_layer_zero=True)
    assert allowed.target_layer == "ETC"
    assert allowed.confidence >= 0.92
