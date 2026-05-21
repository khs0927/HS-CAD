from neuro_seq_cad.config.layer_schema import DEFAULT_LAYERS


def test_generated_review_layers_exist():
    for name in ["WAL_HATCH", "RAW_LINES", "AI_LOWCONF", "QA_MARKUP"]:
        assert name in DEFAULT_LAYERS


def test_wall_hatch_is_separate_hatch_layer():
    spec = DEFAULT_LAYERS["WAL_HATCH"]
    assert spec.is_hatch_layer
    assert spec.name != "WAL1"

