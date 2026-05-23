from __future__ import annotations

import json
from pathlib import Path

from src.graph.networkx_graph_audit import NetworkXGraphAuditor, write_graph_audit


def _graph_payload():
    return {
        'nodes': [
            {'id': 'file:1', 'kind': 'file'},
            {'id': 'area:1', 'kind': 'area'},
            {'id': 'text:1', 'kind': 'text'},
            {'id': 'layer:TXT', 'kind': 'layer', 'predicted_semantic': 'text_note'},
            {'id': 'area:2', 'kind': 'area'},
            {'id': 'text:2', 'kind': 'text'},
        ],
        'edges': [
            {'source': 'file:1', 'target': 'area:1', 'relation': 'HAS_AREA'},
            {'source': 'area:1', 'target': 'text:1', 'relation': 'HAS_LABEL'},
            {'source': 'layer:TXT', 'target': 'area:1', 'relation': 'LAYER_HAS_AREA'},
        ],
    }


def test_networkx_graph_audit_never_raises():
    result = NetworkXGraphAuditor().audit_graph_payload(_graph_payload())
    assert result['status'] in {'ok', 'unavailable'}
    assert result['backend'] == 'networkx_graph_audit'
    assert 'finding_count' in result


def test_networkx_graph_audit_detects_findings_when_available():
    result = NetworkXGraphAuditor().audit_graph_payload(_graph_payload())
    if result['status'] == 'unavailable':
        return
    types = {finding['type'] for finding in result['findings']}
    assert 'unlabeled_area' in types
    assert 'isolated_text' in types
    assert 'layer_semantic_conflict' in types


def test_write_graph_audit_creates_json_and_md(tmp_path: Path):
    (tmp_path / 'SPATIAL_GRAPH.json').write_text(json.dumps(_graph_payload(), ensure_ascii=False), encoding='utf-8')
    result = write_graph_audit(tmp_path)
    assert result['status'] in {'ok', 'unavailable'}
    assert (tmp_path / 'GRAPH_AUDIT.json').exists()
    assert (tmp_path / 'GRAPH_AUDIT.md').exists()
