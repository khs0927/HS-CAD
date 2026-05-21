from neuro_seq_cad.geometry.scale_calibration import DOOR_WIDTH_FALLBACK_CANDIDATES, calibrate_scale, normalize_dimension_text


def test_dimension_text_normalization():
    assert normalize_dimension_text("3,000") == 3000
    assert normalize_dimension_text("3.0m") == 3000
    assert normalize_dimension_text("3000mm") == 3000


def test_door_fallback_candidates_include_common_widths():
    assert set(DOOR_WIDTH_FALLBACK_CANDIDATES) == {800, 850, 900, 1000}


def test_unresolved_scale_uses_identity_with_warning():
    result = calibrate_scale()
    assert result.scale == 1.0
    assert result.source == "identity"
    assert "scale_unresolved" in result.warnings

