"""Tests for the corpus manifest handling."""

from pathlib import Path
import json

from src.corpus.manifest import Manifest


def test_manifest_add_update(tmp_path: Path):
    manifest_path = tmp_path / "manifest.json"
    # Start with empty manifest
    manifest = Manifest()
    entry1 = {
        "file_id": "id1",
        "path": "/tmp/file1.dwg",
        "filename": "file1.dwg",
        "extension": "dwg",
        "size_bytes": 100,
        "modified_time": 1.0,
        "relative_path": "file1.dwg",
        "status": "pending",
        "error_message": None,
    }
    manifest.add_or_update(entry1)
    # Add a second entry with same id but newer timestamp – should replace
    entry1_new = entry1.copy()
    entry1_new["modified_time"] = 2.0
    manifest.add_or_update(entry1_new)
    # Add a different entry
    entry2 = entry1.copy()
    entry2["file_id"] = "id2"
    entry2["path"] = "/tmp/file2.dwg"
    entry2["filename"] = "file2.dwg"
    entry2["modified_time"] = 1.5
    manifest.add_or_update(entry2)
    # Dump and reload
    manifest.dump(manifest_path)
    loaded = Manifest.load(manifest_path)
    # Verify we have two entries and id1 has newer timestamp
    assert len(loaded.records) == 2
    rec_by_id = {r["file_id"]: r for r in loaded.records}
    assert rec_by_id["id1"]["modified_time"] == 2.0
    assert rec_by_id["id2"]["path"] == "/tmp/file2.dwg"
