from pathlib import Path

from src.drawing_fileizers.dwg_libredwg_fileizer import LibreDWGFileizer


def test_libredwg_unavailable_or_available_does_not_raise(tmp_path: Path):
    path = tmp_path / "sample.dwg"
    path.write_bytes(b"not a real dwg")
    record = LibreDWGFileizer().fileize(path, tmp_path / "out")
    assert record.status in {"failed", "unavailable", "partial", "success"}
