from src.cad_core.drawing_standards import (
    CADGenerationStandards,
    cad_unicode_escape,
    recommend_batting_linetype_scale,
    resolve_annotation_style,
)


def test_resolve_annotation_style_prefers_user_request():
    styles = ["Standard", "ISO-25", "복사 ISO-25", "USER-DIM"]

    assert resolve_annotation_style(styles, requested_style="USER-DIM") == "USER-DIM"


def test_resolve_annotation_style_prefers_copy_iso25_before_iso25():
    styles = ["Standard", "ISO-25", "복사 ISO-25"]

    assert resolve_annotation_style(styles) == "복사 ISO-25"


def test_resolve_annotation_style_falls_back_to_iso25():
    assert resolve_annotation_style(["Standard", "ISO-25"]) == "ISO-25"


def test_batting_scale_tracks_insulation_width():
    assert recommend_batting_linetype_scale(100) == 0.08
    assert recommend_batting_linetype_scale(50) == 0.04
    assert recommend_batting_linetype_scale(300) == 0.24


def test_cad_unicode_escape_preserves_ascii_and_encodes_korean():
    assert cad_unicode_escape("50x50 각파이프") == "50x50 \\U+AC01\\U+D30C\\U+C774\\U+D504"


def test_default_standards_match_conversation_rules():
    standards = CADGenerationStandards()

    assert standards.annotation_style == "ISO-25"
    assert standards.preferred_annotation_style == "복사 ISO-25"
    assert standards.batting_linetype == "BATTING"
    assert standards.batting_scale_for_width(100) == 0.08
