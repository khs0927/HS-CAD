from src.corpus.detail_pattern_extractor import infer_detail_patterns
from src.corpus.situation_extractor import extract_situations
from src.corpus.material_extractor import extract_materials
from src.corpus.dimension_extractor import extract_dimensions


def test_infer_panel_hbeam_pattern():
    text = "H빔과 판넬 접합부, 글라스울패널 100T, 후레싱, 실란트"
    patterns = infer_detail_patterns(
        file_id="x",
        situations=extract_situations(text),
        materials=extract_materials(text),
        dimensions=extract_dimensions(text),
    )
    assert patterns
    assert any("접합" in p.pattern_name for p in patterns)
