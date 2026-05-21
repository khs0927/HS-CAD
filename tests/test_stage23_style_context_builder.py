from src.hs_style_context.builder import build_style_context


def test_build_style_context_from_mock_sources():
    local = {
        "recommended_generation_style": {
            "line_layer": "A-WALL",
            "line_color": "256",
            "line_linetype": "ByLayer",
            "lineweight": "-1",
            "text_height": 250,
            "dimension_style": "복사 ISO-25",
        },
        "text_styles": [["지움", 3]],
        "dimension_styles": [["복사 ISO-25", 2]],
        "block_effective_names": [["DOOR_SINGLE", 4]],
    }
    zium = {
        "block_name": "ZIUM_sheet_architect",
        "expected_insert_layer": "A-FORM",
        "representative_usable_area": [10, 20, 1000, 700],
        "scale_distribution": [["0.5/0.5", 1]],
        "block_definition": {
            "title_block_bbox": [700, 0, 1000, 150],
            "usable_drawing_area_bbox": [10, 200, 990, 690],
        },
        "needs_visual_check": False,
    }

    context = build_style_context(local_style_sample=local, zium_sheet_area=zium)

    assert any(pref.preferred_layer == "A-WALL" for pref in context.layer_preferences)
    assert context.sheet_context is not None
    assert context.sheet_context.representative_usable_area == [10, 20, 1000, 700]
    assert context.dimension_style_preferences[0].dimstyle == "복사 ISO-25"
