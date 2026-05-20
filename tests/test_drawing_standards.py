from src.cad_core.drawing_standards import (
    CADGenerationStandards,
    cad_unicode_escape,
    format_measured_dimension,
    insulation_batting_pattern_points,
    insulation_centerline,
    measured_dimension_override,
    qleader_l_route_points,
    recommend_batting_linetype_scale,
    resolve_annotation_style,
    text_box_width,
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
    assert standards.default_dimension_scale == 15.0
    assert any("Do not override dimension text" in note for note in standards.notes)
    assert any("Use QLEADER-style leader entities" in note for note in standards.notes)


def test_dimensions_use_measured_geometry_not_text_override():
    assert measured_dimension_override() == ""
    assert format_measured_dimension(1000) == "1,000"
    assert format_measured_dimension(230) == "230"
    assert format_measured_dimension(12.5) == "12.5"


def test_qleader_route_finishes_with_horizontal_landing_next_to_text():
    label = "브라켓 및 앵커"
    width = text_box_width(label, 34)
    points = qleader_l_route_points((100, 200), (300, 120), width, 34)

    assert points[0] == (100.0, 200.0)
    assert points[1][0] == points[0][0]
    assert points[2][1] == points[1][1]
    assert points[2][0] < 300


def test_qleader_route_handles_left_side_labels():
    width = text_box_width("왼쪽 라벨", 34)
    points = qleader_l_route_points((300, 200), (100, 120), width, 34)

    assert points[1][0] == points[0][0]
    assert points[2][1] == points[1][1]
    assert points[2][0] > 100 + width


def test_insulation_pattern_is_centered_inside_thickness():
    points = insulation_batting_pattern_points((300, 0), 100, 900, vertical=True)
    xs = [x for x, _ in points]

    assert points[0][1] == 0
    assert points[-1][1] == 900
    assert min(xs) >= 300
    assert max(xs) <= 400
    assert (min(xs) + max(xs)) / 2 == 350
    assert insulation_centerline((300, 0), 100, 900, vertical=True) == ((350.0, 0.0), (350.0, 900.0))


def test_horizontal_insulation_pattern_uses_thickness_centerline():
    points = insulation_batting_pattern_points((0, 300), 100, 900, vertical=False)
    ys = [y for _, y in points]

    assert points[0][0] == 0
    assert points[-1][0] == 900
    assert min(ys) >= 300
    assert max(ys) <= 400
    assert (min(ys) + max(ys)) / 2 == 350
    assert insulation_centerline((0, 300), 100, 900, vertical=False) == ((0.0, 350.0), (900.0, 350.0))
