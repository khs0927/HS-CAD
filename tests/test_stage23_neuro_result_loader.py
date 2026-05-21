import json

from src.neuro_seq_cad_bridge.result_loader import iter_neuro_entities, load_neuro_result, normalize_neuro_entity


def test_load_missing_neuro_result_returns_warning(tmp_path):
    result = load_neuro_result(tmp_path / "missing.json")
    assert result["entities"] == []
    assert result["warnings"]


def test_normalize_entity_defaults():
    entity = normalize_neuro_entity({"id": "x1", "type": "wall"})
    assert entity["id"] == "x1"
    assert entity["entity_type"] == "wall"
    assert entity["confidence"] == 0.5
    assert "missing geometry" in entity["warnings"]


def test_iter_entities_from_result():
    result = {"entities": [{"id": "a"}, {"id": "b"}]}
    assert len(iter_neuro_entities(result)) == 2
