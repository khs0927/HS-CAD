import json
from pathlib import Path

from src.qa_visual_review.builder import build_qa_markup


def test_build_qa_markup_from_low_confidence(tmp_path: Path):
    styled = tmp_path / "styled.json"
    styled.write_text(
        json.dumps(
            {
                "entities": [
                    {
                        "original_entity": {
                            "id": "w1",
                            "entity_type": "wall",
                            "confidence": 0.4,
                            "geometry": {"bbox": [0, 0, 10, 10]},
                        },
                        "needs_review": True,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    markup = build_qa_markup(styled)
    assert len(markup.items) == 1
    assert markup.items[0].bbox == [0, 0, 10, 10]
