from src.corpus.dimension_extractor import extract_dimensions


def test_extract_dimensions():
    dims = extract_dimensions("천장고 2564, 방음시창 3000x1000, THK100")
    assert any(d.role == "ceiling_height" for d in dims)
    assert any(d.role == "size_2d" for d in dims)
    assert any(d.role == "thickness" for d in dims)
