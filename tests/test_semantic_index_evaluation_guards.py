from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.corpus.schema import FileizedDrawingRecord
from src.semantic_index.evaluation import evaluate_group_csv
from src.semantic_index.service import SemanticIndexService


def _write_record(path: Path, file_id: str) -> None:
    record = FileizedDrawingRecord(
        file_id=file_id,
        source_path=f"C:/private/{file_id}.dxf",
        relative_path=f"{file_id}.dxf",
        extension=".dxf",
        status="ok",
        engine="test",
        entities=[
            {
                "entity_type": "LINE",
                "layer": "A-WALL",
                "start": [0, 0],
                "end": [1000, 0],
            }
        ],
    )
    path.write_text(
        json.dumps(record.to_dict(), ensure_ascii=False),
        encoding="utf-8",
    )


def test_evaluation_rejects_duplicate_file_id_rows(tmp_path: Path) -> None:
    records = tmp_path / "records"
    records.mkdir()
    _write_record(records / "first.json", "same-id")
    _write_record(records / "second.json", "same-id")
    labels = tmp_path / "labels.csv"
    labels.write_text(
        "record,group\n"
        "records/first.json,A\n"
        "records/second.json,A\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="duplicate file_id"):
        evaluate_group_csv(
            SemanticIndexService(tmp_path / "semantic.sqlite3"),
            labels,
        )


def test_evaluation_rejects_conflicting_group_assignment(tmp_path: Path) -> None:
    records = tmp_path / "records"
    records.mkdir()
    _write_record(records / "first.json", "same-id")
    _write_record(records / "second.json", "same-id")
    labels = tmp_path / "labels.csv"
    labels.write_text(
        "record,group\n"
        "records/first.json,A\n"
        "records/second.json,B\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="multiple groups"):
        evaluate_group_csv(
            SemanticIndexService(tmp_path / "semantic.sqlite3"),
            labels,
        )
