from __future__ import annotations

from pathlib import Path

import pytest

from src.execution.dwg_copy_manager import DWGCopySafetyError, prepare_working_copy
from src.workers.zwcad_copy_validation_worker import (
    run_copy_scan_validation_worker,
    run_copy_saveas_validation_worker,
)


class FakeAdapter:
    def __init__(self):
        self.opened: list[str] = []
        self.saved_as: list[str] = []
        self.warnings = []

    def open_document(self, path: str):
        self.opened.append(path)

    def save_as(self, path: str):
        self.saved_as.append(path)
        Path(path).write_text("fake dwg saveas", encoding="utf-8")

    def scan_modelspace(self):
        return [
            {"handle": "1", "layer": "WAL1", "entity_type": "LINE"},
            {"handle": "2", "layer": "DIM", "entity_type": "DIMENSION"},
        ]


def fake_adapter_factory():
    return FakeAdapter()


def make_fake_dwg(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"fake dwg content")


def test_prepare_working_copy_blocks_same_path(tmp_path: Path):
    original = tmp_path / "a.dwg"
    make_fake_dwg(original)

    with pytest.raises(DWGCopySafetyError):
        prepare_working_copy(original, working_copy_dwg=original)


def test_prepare_working_copy_creates_manifest(tmp_path: Path):
    original = tmp_path / "original.dwg"
    copy = tmp_path / "copy.dwg"
    make_fake_dwg(original)

    manifest = prepare_working_copy(original, working_copy_dwg=copy)

    assert copy.exists()
    assert manifest.original_sha256 == manifest.working_copy_sha256
    assert manifest.safety["original_dwg_mutation_allowed"] is False


def test_copy_scan_validation_worker_writes_artifacts(tmp_path: Path):
    original = tmp_path / "original.dwg"
    copy = tmp_path / "copy.dwg"
    out_dir = tmp_path / "out"
    make_fake_dwg(original)

    result = run_copy_scan_validation_worker(
        original_dwg=str(original),
        working_copy_dwg=str(copy),
        out_dir=out_dir,
        adapter_factory=fake_adapter_factory,
    )

    assert result["status"] == "scan_only_complete"
    assert Path(result["copy_manifest"]).exists()
    assert Path(result["before_scan"]).exists()
    assert Path(result["audit_log"]).exists()


def test_copy_saveas_validation_worker_writes_delta(tmp_path: Path):
    original = tmp_path / "original.dwg"
    copy = tmp_path / "copy.dwg"
    save_as = tmp_path / "saveas" / "result.dwg"
    out_dir = tmp_path / "out"
    make_fake_dwg(original)

    result = run_copy_saveas_validation_worker(
        original_dwg=str(original),
        working_copy_dwg=str(copy),
        save_as_target=str(save_as),
        out_dir=out_dir,
        adapter_factory=fake_adapter_factory,
    )

    assert result["status"] == "saveas_validation_complete"
    assert save_as.exists()
    assert Path(result["before_scan"]).exists()
    assert Path(result["after_scan"]).exists()
    assert Path(result["delta_report"]).exists()
    assert Path(result["audit_log"]).exists()
