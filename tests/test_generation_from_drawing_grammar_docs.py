import pathlib

def test_generation_from_drawing_grammar_docs():
    doc_path = pathlib.Path(__file__).resolve().parents[1] / "docs" / "20_generation_from_drawing_grammar.md"
    assert doc_path.is_file()
    content = doc_path.read_text(encoding="utf-8")
    # Key phrases that must be present
    assert "Do not remap layers unless explicitly requested" in content
    assert "ZIUM_sheet_architect" in content
    assert "usable drawing area" in content
    assert "sample nearby authored geometry" in content
