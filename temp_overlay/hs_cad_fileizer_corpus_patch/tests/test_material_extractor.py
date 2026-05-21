from src.corpus.material_extractor import extract_materials


def test_extract_materials_panel_and_steel():
    mentions = extract_materials("H빔 접합부에 글라스울패널 100T와 실란트 코킹 적용")
    names = [m.material_name for m in mentions]
    assert any("H" in n or "빔" in n for n in names)
    assert any("글라스울" in n for n in names)
    assert any("실란트" in n for n in names)
