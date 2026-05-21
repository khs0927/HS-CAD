from src.hs_style_context.builder import build_style_context
from src.hs_style_context.resolver import resolve_style
from src.hs_style_context.schema import StyleResolveRequest


def _context():
    return build_style_context(
        local_style_sample={
            "recommended_generation_style": {
                "line_layer": "A-WALL",
                "line_linetype": "ByLayer",
                "line_color": 256,
            }
        }
    )


def test_wall_uses_local_layer():
    result = resolve_style(StyleResolveRequest(element_type="wall", confidence=0.9), _context())
    assert result.target_layer == "A-WALL"
    assert not result.needs_review


def test_raw_line_existing_preview_is_isolated():
    result = resolve_style(
        StyleResolveRequest(element_type="raw_line", confidence=0.9, mode="existing_dwg_preview"),
        _context(),
    )
    assert result.target_layer == "QA-REVIEW"


def test_low_confidence_needs_review():
    result = resolve_style(StyleResolveRequest(element_type="wall", confidence=0.3), _context())
    assert result.needs_review
