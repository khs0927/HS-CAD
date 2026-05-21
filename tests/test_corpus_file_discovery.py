"""Tests for the corpus file discovery utilities."""

from pathlib import Path
import tempfile

from src.corpus.file_discovery import discover_files, file_metadata


def test_discover_and_metadata(tmp_path: Path):
    # Create a mix of files, some should be ignored
    (tmp_path / "a.dwg").write_text("dummy")
    (tmp_path / "b.pdf").write_text("dummy")
    (tmp_path / "c.txt").write_text("dummy")
    (tmp_path / "~$temp.docx").write_text("should be ignored")
    (tmp_path / ".hidden.dxf").write_text("should be ignored too")

    files = list(discover_files(tmp_path))
    # Expect only the three supported files (dwg, pdf, txt)
    assert len(files) == 3
    paths = {p.name for p in files}
    assert paths == {"a.dwg", "b.pdf", "c.txt"}

    # Verify metadata contains expected keys
    meta = file_metadata(tmp_path, files[0])
    required_keys = {
        "file_id",
        "path",
        "filename",
        "extension",
        "size_bytes",
        "modified_time",
        "relative_path",
        "guessed_project_name",
        "guessed_drawing_category",
        "status",
        "error_message",
    }
    assert required_keys.issubset(set(meta.keys()))
