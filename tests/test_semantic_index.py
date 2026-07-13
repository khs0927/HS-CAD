from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from src.corpus.schema import FileizedDrawingRecord
from src.semantic_index.features import FEATURE_VERSION, GeometryFeatureExtractor
from src.semantic_index.service import SemanticIndexService


def _record(file_id: str, relative_path: str, *, rotated: bool = False, include_text: bool = False) -> FileizedDrawingRecord:
    line_a = {'entity_type': 'LINE', 'layer': 'A-WALL', 'start': [0, 0], 'end': [10, 0]}
    line_b = {'entity_type': 'LINE', 'layer': 'A-WALL', 'start': [0, 0], 'end': [0, 10]}
    if rotated:
        line_a = {'entity_type': 'LINE', 'layer': 'A-WALL', 'start': [0, 0], 'end': [0, 10]}
        line_b = {'entity_type': 'LINE', 'layer': 'A-WALL', 'start': [0, 0], 'end': [-10, 0]}
    entities = [
        line_a,
        line_b,
        {'entity_type': 'LWPOLYLINE', 'layer': 'A-WALL', 'closed': True, 'vertices': [[0, 0], [10, 0], [10, 10], [0, 10]]},
        {'entity_type': 'INSERT', 'layer': 'A-DOOR', 'name': 'D01', 'insert': [5, 0]},
    ]
    texts = []
    if include_text:
        entities.append({'entity_type': 'TEXT', 'layer': 'A-TEXT', 'text': '기계실', 'insert': [2, 2]})
        texts.append({'entity_type': 'TEXT', 'layer': 'A-TEXT', 'text': '기계실'})
    return FileizedDrawingRecord(
        file_id=file_id,
        source_path=f'C:/{relative_path}',
        relative_path=relative_path,
        extension='.dxf',
        status='ok',
        engine='test',
        layers=[{'name': 'A-WALL', 'entity_count': 3}, {'name': 'A-DOOR', 'entity_count': 1}],
        blocks=[{'name': 'D01', 'count': 1}],
        entities=entities,
        texts=texts,
    )


def _write(path: Path, record: FileizedDrawingRecord) -> None:
    path.write_text(json.dumps(record.to_dict(), ensure_ascii=False), encoding='utf-8')


def test_geometry_vector_is_normalized_and_stable() -> None:
    vector = GeometryFeatureExtractor().extract(_record('a', 'a.dxf'))
    assert vector.feature_version == FEATURE_VERSION
    assert vector.metadata['text_ignored'] is True
    assert vector.metadata['vector_dimensions'] == len(vector.vector)
    assert np.isclose(np.linalg.norm(np.asarray(vector.vector)), 1.0)


def test_text_content_does_not_change_geometry_vector() -> None:
    extractor = GeometryFeatureExtractor()
    without_text = extractor.extract(_record('a', 'a.dxf', include_text=False))
    with_text = extractor.extract(_record('b', 'b.dxf', include_text=True))
    # TEXT entities are intentionally mapped to OTHER only when present, so the
    # actual string value is ignored. Removing a text object changes geometry
    # inventory, but changing its content must not.
    changed_text = _record('c', 'c.dxf', include_text=True)
    changed_text.entities[-1]['text'] = '전혀 다른 문자'
    changed_text.texts[-1]['text'] = '전혀 다른 문자'
    changed = extractor.extract(changed_text)
    assert with_text.vector == changed.vector
    assert without_text.vector != with_text.vector


def test_build_and_query_local_index(tmp_path: Path) -> None:
    records = tmp_path / 'records'
    records.mkdir()
    first = _record('a', 'a.dxf')
    second = _record('b', 'b.dxf', rotated=True)
    _write(records / 'a.json', first)
    _write(records / 'b.json', second)

    service = SemanticIndexService(tmp_path / 'semantic.sqlite3')
    result = service.build_from_json_dir(records)
    assert result['indexed'] == 2
    assert result['total_in_index'] == 2

    hits = service.search_record(records / 'a.json', limit=5)
    assert len(hits) == 1
    assert hits[0].file_id == 'b'
    assert -1.0 <= hits[0].score <= 1.0
