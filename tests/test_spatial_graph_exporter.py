from __future__ import annotations

import json
from pathlib import Path

from src.spatial.graph_exporter import SpatialGraphExporter


def test_spatial_graph_exporter_record_links_area_to_label_text_and_layers():
    record = {
        'file_id': 'room',
        'relative_path': 'room.dxf',
        'entities': [
            {'handle': 'P1', 'entity_type': 'POLYLINE', 'layer': 'ROOM', 'closed': True, 'points': [[0, 0], [10, 0], [10, 10], [0, 10]]},
            {'handle': 'T1', 'entity_type': 'TEXT', 'layer': 'TEXT', 'text': '사무실', 'insert': [5, 5]},
        ],
    }
    graph = SpatialGraphExporter(area_backend='pure').export_record(record)
    assert graph['node_count'] >= 5
    assert graph['edge_count'] >= 6
    edge_relations = {edge['relation'] for edge in graph['edges']}
    assert 'HAS_TEXT' in edge_relations
    assert 'HAS_AREA' in edge_relations
    assert 'HAS_LABEL' in edge_relations
    assert 'HAS_LAYER' in edge_relations
    assert 'LAYER_HAS_TEXT' in edge_relations
    assert 'LAYER_HAS_AREA' in edge_relations
    kinds = {node['kind'] for node in graph['nodes']}
    assert {'file', 'text', 'area', 'layer'} <= kinds


def test_spatial_graph_exporter_json_dir_includes_layer_counts(tmp_path: Path):
    json_dir = tmp_path / 'fileized' / 'json'
    json_dir.mkdir(parents=True)
    record = {
        'file_id': 'sample',
        'relative_path': 'sample.dxf',
        'entities': [
            {'handle': 'P1', 'entity_type': 'POLYLINE', 'layer': 'ROOM', 'closed': True, 'points': [[0, 0], [5, 0], [5, 5], [0, 5]]},
            {'handle': 'T1', 'entity_type': 'TEXT', 'layer': 'TEXT', 'text': '실명', 'insert': [2, 2]},
        ],
    }
    (json_dir / 'sample.json').write_text(json.dumps(record, ensure_ascii=False), encoding='utf-8')
    graph = SpatialGraphExporter(area_backend='pure').export_json_dir(json_dir)
    assert graph['file_count'] == 1
    assert graph['node_kind_counts']['file'] == 1
    assert graph['node_kind_counts']['text'] == 1
    assert graph['node_kind_counts']['area'] == 1
    assert graph['node_kind_counts']['layer'] == 2
    assert graph['edge_relation_counts']['HAS_LABEL'] == 1
    assert graph['edge_relation_counts']['HAS_LAYER'] == 2
    assert graph['edge_relation_counts']['LAYER_HAS_TEXT'] == 1
    assert graph['edge_relation_counts']['LAYER_HAS_AREA'] == 1
