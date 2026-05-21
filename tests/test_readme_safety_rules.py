import pathlib

def test_readme_safety_rules():
    readme_path = pathlib.Path(__file__).resolve().parents[1] / "README.md"
    content = readme_path.read_text(encoding="utf-8")
    # New safety rule bullet points must be present
    assert "When editing an existing office DWG, prefer the sampled local layer and visual grammar." in content
    assert "Do not remap existing layers unless explicitly requested." in content
    assert "Use explicit generated layers only for standalone generated drawings or review-isolation workflows." in content
    # Old bullet must be removed
    assert "Keep generated layers explicit" not in content
