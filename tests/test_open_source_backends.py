from __future__ import annotations

import json
from pathlib import Path

from src.integrations.open_source_backends import OpenSourceBackendRegistry


def test_open_source_backend_registry_loads_config(tmp_path: Path):
    config = tmp_path / 'backends.json'
    config.write_text(json.dumps({
        'version': 1,
        'backends': [
            {
                'id': 'json',
                'capability': 'stdlib',
                'python_import': 'json',
                'purpose': 'test stdlib import',
                'required': False,
                'planned_pr': 'test',
            },
            {
                'id': 'definitely_missing_backend',
                'capability': 'missing',
                'python_import': 'definitely_missing_backend_xyz',
                'purpose': 'test missing import',
                'required': False,
                'planned_pr': 'test',
            },
        ],
    }), encoding='utf-8')

    summary = OpenSourceBackendRegistry(config).summary()
    assert summary['backend_count'] == 2
    assert summary['available_count'] == 1
    assert summary['missing_optional_count'] == 1
    statuses = {item['id']: item for item in summary['backends']}
    assert statuses['json']['available'] is True
    assert statuses['definitely_missing_backend']['available'] is False


def test_project_open_source_backend_config_contains_expected_backends():
    summary = OpenSourceBackendRegistry('config/open_source_backends.json').summary()
    ids = {item['id'] for item in summary['backends']}
    assert 'shapely' in ids
    assert 'networkx' in ids
    assert 'duckdb' in ids
    assert 'opencv' in ids
    assert 'ifcopenshell' in ids
