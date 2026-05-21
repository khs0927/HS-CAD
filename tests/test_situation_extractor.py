from src.corpus.situation_extractor import extract_situations


def test_extract_situations():
    situations = extract_situations("H빔과 판넬 접합부에 후레싱, 실란트, 하지철물 적용")
    tags = [s.tag for s in situations]
    assert "판넬마감" in tags
    assert "H빔접합" in tags
