from pathlib import Path


def test_image_to_cad_docs_cover_required_policy():
    doc = Path("docs/21_image_to_cad_pipeline.md")
    text = doc.read_text(encoding="utf-8")
    assert doc.exists()
    assert "수정 가능한 CAD 초안" in text or "Editable CAD Draft" in text
    assert "900mm" in text and "fallback" in text
    assert "WAL_HATCH" in text
    assert "RAW_LINES" in text
    assert "AI_LOWCONF" in text
    assert "license" in text or "라이선스" in text

