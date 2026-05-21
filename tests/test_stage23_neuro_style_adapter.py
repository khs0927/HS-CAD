from src.hs_style_context.builder import build_style_context
from src.neuro_seq_cad_bridge.style_adapter import apply_style_context_to_neuro_result


def test_apply_style_context_to_neuro_result():
    context = build_style_context(
        local_style_sample={"recommended_generation_style": {"line_layer": "A-WALL"}}
    )
    neuro = {
        "entities": [
            {"id": "w1", "entity_type": "wall", "geometry": {"type": "line"}, "confidence": 0.9},
            {"id": "l1", "entity_type": "raw_line", "geometry": {"type": "line"}, "confidence": 0.9},
        ]
    }
    styled = apply_style_context_to_neuro_result(neuro, context, mode="existing_dwg_preview")
    assert len(styled["entities"]) == 2
    assert styled["entities"][0]["target_layer"] == "A-WALL"
    assert styled["entities"][1]["target_layer"] == "QA-REVIEW"
