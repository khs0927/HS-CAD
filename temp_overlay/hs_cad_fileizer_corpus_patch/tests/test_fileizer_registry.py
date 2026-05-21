from pathlib import Path

from src.drawing_fileizers.fileizer_registry import FileizerRegistry


def test_registry_selects_dxf_fileizer():
    registry = FileizerRegistry()
    candidates = registry.candidates_for(Path("sample.dxf"))
    assert candidates
    assert candidates[0].get_name() == "ezdxf"


def test_registry_handles_unknown_extension():
    registry = FileizerRegistry()
    assert registry.best_for(Path("sample.unknown")) is None
