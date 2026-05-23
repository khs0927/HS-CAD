from __future__ import annotations

import json
from pathlib import Path

from src.analysis.layer_audit import LayerSemanticsAuditor, layer_audit_markdown, write_layer_audit
from src.analysis.layer_semantics import LayerSemanticInferer


def test_layer_audit_flags_unknown_and_low_confidence_layers():
    result = {
        'json_dir': 'memory',
        'file_count': 1,
        'layer_count': 2,
        'layers': [
            {
                'layer': 'UNKNOWN_LAYER',
                'predicted_semantic': 'unknown',
                'confidence': 0.2,
                'evidence': [],
                'counts': {'entity_types': {'LINE': 1}},
            },
            {
                'layer': 'A-WALL',
                'predicted_semantic': 'wall',
                'confidence': 0.75,
                'evidence': ['layer name matches wall'],
                'counts': {'entity_types': {'LINE': 10}},
            },
        ],
    }
    audit = LayerSemanticsAuditor().audit_result(result)
    assert audit['finding_count'] >= 2
    types = {item['type'] for item in audit['findings']}
    assert 'unknown_layer_semantic' in types
    assert 'low_confidence_layer_semantic' in types
    assert audit['calibration_todo']['company_specific_mapping_deferred'] is True


def test_layer_audit_markdown_contains_calibration_todo():
    audit = {
        'file_count': 1,
        'layer_count': 1,
        'finding_count': 1,
        'severity_counts': {'medium': 1},
        'finding_type_counts': {'unknown_layer_semantic': 1},
        'findings': [
            {
                'severity': 'medium',
                'type': 'unknown_layer_semantic',
                'message': 'review',
                'layer': {'layer': 'X', 'predicted_semantic': 'unknown', 'confidence': 0.2},
            }
        ],
    }
    md = layer_audit_markdown(audit)
    assert 'Company-specific layer mapping is intentionally deferred' in md
    assert 'unknown_layer_semantic' in md


def test_write_layer_audit_creates_json_and_md(tmp_path: Path):
    workspace = tmp_path
    json_dir = workspace / 'fileized' / 'json'
    json_dir.mkdir(parents=True)
    record = {'file_id': 'sample', 'entities': [{'entity_type': 'LINE', 'layer': 'MYSTERY'}]}
    (json_dir / 'sample.json').write_text(json.dumps(record, ensure_ascii=False), encoding='utf-8')
    result = write_layer_audit(workspace)
    assert result['finding_count'] >= 1
    assert (workspace / 'LAYER_AUDIT.json').exists()
    assert (workspace / 'LAYER_AUDIT.md').exists()
