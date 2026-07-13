from __future__ import annotations

from pathlib import Path

from src.corpus.indexer import CorpusIndexer
from src.corpus.query import CorpusQuery
from src.corpus.schema import FileizedDrawingRecord, text_rows_from_entities
from src.corpus.text_extraction import normalize_search_text, plain_cad_text


def test_plain_cad_text_decodes_mtext_and_symbols() -> None:
    raw = r"{\C1;방화문\P900%%d\U+00B1}"
    plain = plain_cad_text(raw)
    assert "방화문" in plain
    assert "900°±" in plain
    assert normalize_search_text(raw) == normalize_search_text(plain)


def test_text_rows_expand_all_cad_text_sources() -> None:
    entities = [
        {
            "handle": "1A",
            "entity_type": "MTEXT",
            "layer": "A-ANNO",
            "layout": "Model",
            "space": "model",
            "text": r"{\H2.5x;방화구획\P벽체}",
            "insert": [10, 20, 0],
        },
        {
            "handle": "2B",
            "entity_type": "INSERT",
            "layer": "A-DOOR",
            "layout": "1층 평면도",
            "space": "paper",
            "block_path": ["DOOR_TAG"],
            "attributes": [
                {
                    "handle": "2C",
                    "tag": "DOOR_NO",
                    "text": "D-101",
                    "insert": [30, 40, 0],
                }
            ],
            "constant_attributes": [{"tag": "RATING", "text": "1시간 내화"}],
        },
        {
            "handle": "3C",
            "entity_type": "DIMENSION",
            "layer": "A-DIMS",
            "layout": "Model",
            "measurement": 1200.0,
            "text_override": "",
        },
        {
            "handle": "4D",
            "entity_type": "TABLE",
            "layer": "A-SCHEDULE",
            "layout": "문일람표",
            "table_cells": [
                {"row": 0, "column": 0, "text": "문번호"},
                {"row": 1, "column": 0, "text": "D-101"},
            ],
        },
        {
            "handle": "5E",
            "entity_type": "MLEADER",
            "layer": "A-NOTE",
            "layout": "Model",
            "leader_texts": ["준불연 단열재"],
        },
    ]
    rows = text_rows_from_entities(entities)
    texts = {row["text"] for row in rows}
    assert "방화구획\n벽체" in texts
    assert "D-101" in texts
    assert "1시간 내화" in texts
    assert "1200.0" in texts
    assert "문번호" in texts
    assert "준불연 단열재" in texts
    assert all(row["occurrence_id"] for row in rows)
    assert any(row["layout"] == "1층 평면도" for row in rows)
    assert any(row["source_kind"] == "block_attribute" for row in rows)


def test_v2_index_preserves_evidence_location(tmp_path: Path) -> None:
    entities = [
        {
            "handle": "AA",
            "entity_type": "MTEXT",
            "layer": "A-ANNO",
            "layout": "2층 평면도",
            "space": "paper",
            "block_path": ["SHEET", "NOTE"],
            "text": "방화구획 벽체",
            "insert": [1250.5, 830.25, 0],
        }
    ]
    record = FileizedDrawingRecord(
        file_id="sample",
        source_path=r"C:\drawings\A-201.dwg",
        relative_path="A-201.dwg",
        extension=".dwg",
        status="ok",
        engine="test",
        entities=entities,
        texts=text_rows_from_entities(entities),
        layouts=[{"name": "2층 평면도", "space": "paper"}],
        extraction_report={"complete": True, "text_occurrence_count": 1},
    )
    db = tmp_path / "index.sqlite"
    CorpusIndexer(db).index_record(record)
    result = CorpusQuery(db).search_text("방화구획")
    assert result["matches"]
    match = result["matches"][0]
    assert match["layout"] == "2층 평면도"
    assert match["layer"] == "A-ANNO"
    assert match["handle"] == "AA"
    assert match["block_path"] == ["SHEET", "NOTE"]
    assert match["x"] == 1250.5
