from src.hs_style_context.schema import LayerPreference, SheetContext, StyleContext, StyleResolveResult


def test_style_context_schema_creation():
    context = StyleContext()
    context.layer_preferences.append(
        LayerPreference(role="wall", preferred_layer="A-WALL", confidence=0.9, source="test")
    )
    context.sheet_context = SheetContext(
        sheet_block_name="ZIUM_sheet_architect",
        insert_layer="A-FORM",
        representative_usable_area=[0, 0, 1000, 700],
        needs_visual_check=False,
        confidence=0.8,
        source="test",
    )

    assert context.layer_preferences[0].preferred_layer == "A-WALL"
    assert context.sheet_context.sheet_block_name == "ZIUM_sheet_architect"


def test_style_resolve_result_creation():
    result = StyleResolveResult(element_type="wall", target_layer="A-WALL")
    assert result.target_layer == "A-WALL"
