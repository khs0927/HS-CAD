from __future__ import annotations

import json
import math
from pathlib import Path

import pytest

from src.corpus.schema import FileizedDrawingRecord
from src.semantic_index.features import GeometryFeatureExtractor
from src.semantic_index.service import SemanticIndexService


def _record(
    file_id: str,
    *,
    entities: list[dict],
    blocks: list[dict] | None = None,
    complete: bool | None = None,
) -> FileizedDrawingRecord:
    report = {} if complete is None else {"complete": complete}
    return FileizedDrawingRecord(
        file_id=file_id,
        source_path=f"C:/private/{file_id}.dxf",
        relative_path=f"{file_id}.dxf",
        extension=".dxf",
        status="ok",
        engine="test",
        entities=entities,
        blocks=list(blocks or []),
        extraction_report=report,
    )


def _write(path: Path, record: FileizedDrawingRecord) -> None:
    path.write_text(
        json.dumps(record.to_dict(), ensure_ascii=False),
        encoding="utf-8",
    )


def test_text_only_block_summaries_do_not_create_geometry() -> None:
    record = _record(
        "text-only",
        entities=[
            {
                "entity_type": "TEXT",
                "layer": "A-TEXT",
                "text": "기계실",
                "insert": [10, 10],
            }
        ],
        blocks=[{"name": "TEXT_NOTE_BLOCK", "count": 500}],
    )

    vector = GeometryFeatureExtractor().extract(record)

    assert all(abs(value) <= 1e-12 for value in vector.vector)
    assert vector.metadata["entity_count"] == 0
    assert vector.metadata["block_count"] == 0


def test_block_table_metadata_does_not_change_geometry_vector() -> None:
    entities = [
        {
            "entity_type": "LINE",
            "layer": "A-WALL",
            "start": [0, 0],
            "end": [1000, 0],
        },
        {
            "entity_type": "INSERT",
            "layer": "A-DOOR",
            "name": "D01",
            "insert": [500, 0],
        },
    ]
    plain = _record("plain", entities=entities)
    noisy = _record(
        "noisy",
        entities=entities,
        blocks=[
            {"name": "TEXT_ONLY", "count": 9999},
            {"name": "ANNOTATION_ONLY", "count": 8888},
        ],
    )

    assert GeometryFeatureExtractor().extract(plain).vector == GeometryFeatureExtractor().extract(noisy).vector


def test_non_finite_coordinates_never_produce_non_finite_vector() -> None:
    record = _record(
        "non-finite",
        entities=[
            {
                "entity_type": "LINE",
                "layer": "A-WALL",
                "start": [0, 0],
                "end": [float("nan"), float("inf")],
            }
        ],
    )

    vector = GeometryFeatureExtractor().extract(record)

    assert vector.vector
    assert all(math.isfinite(value) for value in vector.vector)


def test_explicitly_incomplete_record_is_skipped_and_rejected_as_query(
    tmp_path: Path,
) -> None:
    records = tmp_path / "records"
    records.mkdir()
    path = records / "incomplete.json"
    record = _record(
        "incomplete",
        complete=False,
        entities=[
            {
                "entity_type": "LINE",
                "layer": "A-WALL",
                "start": [0, 0],
                "end": [1000, 0],
            }
        ],
    )
    _write(path, record)
    service = SemanticIndexService(tmp_path / "semantic.sqlite3")

    result = service.build_from_json_dir(records)

    assert result["indexed"] == 0
    assert result["skipped"] == 1
    assert result["incomplete_records"] == [str(path)]
    with pytest.raises(ValueError, match="explicitly incomplete"):
        service.search_record(path)
