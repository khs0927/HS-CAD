from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from src.corpus.schema import FileizedDrawingRecord
from src.semantic_index.evaluation import evaluate_group_csv
from src.semantic_index.features import FEATURE_VERSION, GeometryFeatureExtractor
from src.semantic_index.service import SemanticIndexService


def _record(file_id: str, relative_path: str, *, rotated: bool = False, include_text: bool = False) -> FileizedDrawingRecord:
    line_a = {'entity_type': 'LINE', 'layer': 'A-WALL', 'start': [0, 0], 'end': [10, 0]}
    line_b = {'entity_type': 'LINE', 'layer': 'A-WALL', 'start': [0, 0], 'end': [0, 10]}
    if rotated:
        line_a = {'entity_type': 'LINE', 'layer': 'A-WALL', 'start': [0, 0], 'end': [10, 10]}
        line_b = {'entity_type': 'LINE', 'layer': 'A-WALL', 'start': [0, 0], 'end': [-10, 10]}
    entities = [
        line_a,
        line_b,
        {'entity_type': 'LWPOLYLINE', 'layer': 'A-WALL', 'closed': True, 'vertices': [[0, 0], [10, 0], [10, 10], [0, 10]]},
        {'entity_type': 'INSERT', 'layer': 'A-DOOR', 'name': 'D01', 'insert': [5, 0]},
    ]
    texts = []
    layers = [{'name': 'A-WALL', 'entity_count': 3}, {'name': 'A-DOOR', 'entity_count': 1}]
    if include_text:
        entities.append({'entity_type': 'TEXT', 'layer': 'A-TEXT', 'text': '기계실', 'insert': [2000, 2000]})
        texts.append({'entity_type': 'TEXT', 'layer': 'A-TEXT', 'text': '기계실'})
        layers.append({'name': 'A-TEXT', 'entity_count': 100})
    return FileizedDrawingRecord(
        file_id=file_id,
        source_path=f'C:/{relative_path}',
        relative_path=relative_path,
        extension='.dxf',
        status='ok',
        engine='test',
        layers=layers,
        blocks=[{'name': 'D01', 'count': 1}],
        entities=entities,
        texts=texts,
    )


def _empty_record(file_id: str, relative_path: str) -> FileizedDrawingRecord:
    return FileizedDrawingRecord(
        file_id=file_id,
        source_path=f'C:/{relative_path}',
        relative_path=relative_path,
        extension='.dxf',
        status='ok',
        engine='test',
    )


def _write(path: Path, record: FileizedDrawingRecord) -> None:
    path.write_text(json.dumps(record.to_dict(), ensure_ascii=False), encoding='utf-8')


def test_geometry_vector_is_normalized_and_stable() -> None:
    vector = GeometryFeatureExtractor().extract(_record('a', 'a.dxf'))
    assert vector.feature_version == FEATURE_VERSION
    assert vector.metadata['text_ignored'] is True
    assert vector.metadata['vector_dimensions'] == len(vector.vector)
    assert np.isclose(np.linalg.norm(np.asarray(vector.vector)), 1.0)


def test_text_entities_do_not_change_geometry_vector() -> None:
    extractor = GeometryFeatureExtractor()
    without_text = extractor.extract(_record('a', 'a.dxf', include_text=False))
    with_text = extractor.extract(_record('b', 'b.dxf', include_text=True))
    changed_text = _record('c', 'c.dxf', include_text=True)
    changed_text.entities[-1]['text'] = '전혀 다른 문자'
    changed_text.texts[-1]['text'] = '전혀 다른 문자'
    changed = extractor.extract(changed_text)

    assert without_text.vector == with_text.vector == changed.vector
    assert with_text.metadata['ignored_text_entity_count'] == 1
    assert with_text.metadata['entity_count'] == without_text.metadata['entity_count']
    assert with_text.metadata['layer_count'] == without_text.metadata['layer_count']


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


def test_empty_geometry_is_skipped_and_cannot_be_queried(tmp_path: Path) -> None:
    records = tmp_path / 'records'
    records.mkdir()
    path = records / 'empty.json'
    _write(path, _empty_record('empty', 'empty.dxf'))

    service = SemanticIndexService(tmp_path / 'semantic.sqlite3')
    result = service.build_from_json_dir(records)
    assert result['indexed'] == 0
    assert result['skipped'] == 1
    assert result['empty_geometry'] == [str(path)]
    with pytest.raises(ValueError, match='no indexable geometry'):
        service.search_record(path)


def test_equal_scores_are_ordered_by_file_id(tmp_path: Path) -> None:
    records = tmp_path / 'records'
    records.mkdir()
    for file_id in ('a', 'b', 'c'):
        _write(records / f'{file_id}.json', _record(file_id, f'{file_id}.dxf'))

    service = SemanticIndexService(tmp_path / 'semantic.sqlite3')
    service.build_from_json_dir(records)
    hits = service.search_record(records / 'a.json', limit=2)
    assert [hit.file_id for hit in hits] == ['b', 'c']


def test_group_csv_evaluation_reports_perfect_top1(tmp_path: Path) -> None:
    records = tmp_path / 'records'
    records.mkdir()
    a1 = _record('a1', 'a1.dxf')
    a2 = _record('a2', 'a2.dxf')
    b1 = _record('b1', 'b1.dxf', rotated=True)
    b2 = _record('b2', 'b2.dxf', rotated=True)
    for record in (a1, a2, b1, b2):
        _write(records / f'{record.file_id}.json', record)

    service = SemanticIndexService(tmp_path / 'semantic.sqlite3')
    service.build_from_json_dir(records)
    labels = tmp_path / 'labels.csv'
    labels.write_text(
        'record,group\n'
        'records/a1.json,A\n'
        'records/a2.json,A\n'
        'records/b1.json,B\n'
        'records/b2.json,B\n',
        encoding='utf-8',
    )

    report = evaluate_group_csv(service, labels, top_k=1)
    assert report['evaluated_queries'] == 4
    assert report['precision_at_1'] == 1.0
    assert report['recall_at_1'] == 1.0
    assert report['hit_at_1'] == 1.0
