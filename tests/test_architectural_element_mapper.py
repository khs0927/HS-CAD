from src.corpus.architectural_element_mapper import map_to_canonical_elements


def test_map_layers_to_canonical():
    out = map_to_canonical_elements(["WAL1", "COL", "300DIM", "방음시창"])
    elems = {o.canonical_element for o in out}
    assert "WALL" in elems
    assert "COLUMN" in elems
    assert "DIMENSION" in elems or "WINDOW" in elems
