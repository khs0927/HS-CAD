from __future__ import annotations

import json
from pathlib import Path

from src.integrations.cad_platforms import CADPlatformRegistry


def test_cad_platform_registry_loads_expected_platforms():
    summary = CADPlatformRegistry('config/cad_platforms.json').summary()
    ids = {item['id'] for item in summary['platforms']}
    assert {'autocad', 'zwcad', 'gstarcad', 'bricscad', 'oda_file_converter', 'libredwg', 'ezdxf'} <= ids
    assert isinstance(summary['preferred_analysis_path'], list)


def test_cad_platform_registry_prefers_oda_before_cad_and_ezdxf(tmp_path: Path, monkeypatch):
    oda = tmp_path / 'ODAFileConverter.exe'
    oda.write_text('', encoding='utf-8')
    monkeypatch.setenv('ODA_FILE_CONVERTER', str(oda))
    monkeypatch.setenv('HSCAD_ZWCAD_AVAILABLE', '1')

    config = tmp_path / 'platforms.json'
    config.write_text(json.dumps({
        'platforms': [
            {'id': 'ezdxf', 'display_name': 'ezdxf', 'capabilities': [], 'analysis_role': '', 'required_for_analysis': True},
            {'id': 'zwcad', 'display_name': 'ZWCAD', 'capabilities': [], 'analysis_role': '', 'required_for_analysis': False},
            {'id': 'oda_file_converter', 'display_name': 'ODA', 'capabilities': [], 'analysis_role': '', 'required_for_analysis': False},
        ]
    }), encoding='utf-8')

    path = CADPlatformRegistry(config).summary()['preferred_analysis_path']
    assert path[0] == 'oda_file_converter'
    assert 'zwcad' in path
    assert 'ezdxf' in path


def test_cad_platform_registry_cad_env_flags_are_optional(monkeypatch):
    monkeypatch.delenv('HSCAD_AUTOCAD_AVAILABLE', raising=False)
    summary = CADPlatformRegistry('config/cad_platforms.json').summary()
    autocad = next(item for item in summary['platforms'] if item['id'] == 'autocad')
    assert autocad['available'] is False
    assert 'not set' in autocad['reason']
