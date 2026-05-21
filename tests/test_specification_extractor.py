from src.corpus.specification_extractor import extract_specifications


def test_extract_specs():
    specs = extract_specifications("방음시창 3000x1000, 판넬 125T, 열관류율 1.8W/m2K")
    assert any(s.spec_type == "width_height" for s in specs)
    assert any(s.spec_type == "thickness" for s in specs)
    assert any(s.spec_type == "thermal_transmittance" for s in specs)
