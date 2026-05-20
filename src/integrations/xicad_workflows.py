from __future__ import annotations

from typing import Any

WORKFLOWS: dict[str, dict[str, Any]] = {
    'wall': {
        'name': 'wall',
        'alias': 'WAL',
        'description': '벽 그리기. AI가 바운더리/그리드/레이어를 준비한 뒤 XiCAD WAL을 실행합니다.',
        'preflight_layers': ['A-WALL', 'A-GRID', 'A-BOUNDARY'],
        'post_checks': ['scan_layers', 'check_wall_layer_count'],
    },
    'column': {
        'name': 'column',
        'alias': 'COL',
        'description': '기둥 그리기. 그리드 교차점 후보를 만든 뒤 XiCAD COL을 실행합니다.',
        'preflight_layers': ['A-COLUMN', 'A-GRID'],
        'post_checks': ['scan_blocks', 'generate_quantity_report'],
    },
    'door_simple': {
        'name': 'door_simple',
        'alias': 'D1',
        'description': '간단문 그리기. 벽체와 삽입 기준점을 준비한 뒤 XiCAD D1을 실행합니다.',
        'preflight_layers': ['A-WALL', 'A-DOOR'],
        'post_checks': ['scan_blocks'],
    },
    'window_simple': {
        'name': 'window_simple',
        'alias': 'W1',
        'description': '간단창 그리기. 벽체와 창호 삽입 기준점을 준비한 뒤 XiCAD W1을 실행합니다.',
        'preflight_layers': ['A-WALL', 'A-WINDOW'],
        'post_checks': ['scan_blocks'],
    },
    'parking': {
        'name': 'parking',
        'alias': 'PK',
        'description': '주차장 그리기. 대지/주차 구획 바운더리를 준비한 뒤 XiCAD PK를 실행합니다.',
        'preflight_layers': ['A-PARKING', 'A-BOUNDARY'],
        'post_checks': ['scan_blocks', 'scan_layers'],
    },
    'stair_plan': {
        'name': 'stair_plan',
        'alias': 'STP',
        'description': '계단 평면 그리기. 계단실 바운더리를 준비한 뒤 XiCAD STP를 실행합니다.',
        'preflight_layers': ['A-STAIR', 'A-BOUNDARY'],
        'post_checks': ['scan_blocks', 'scan_layers'],
    },
    'elevator': {
        'name': 'elevator',
        'alias': 'ELV',
        'description': '엘리베이터 그리기. 샤프트 기준 영역을 준비한 뒤 XiCAD ELV를 실행합니다.',
        'preflight_layers': ['A-ELEVATOR', 'A-BOUNDARY'],
        'post_checks': ['scan_blocks'],
    },
    'insulation': {
        'name': 'insulation',
        'alias': 'INS',
        'description': '단열재 그리기. 외벽/단열 라인을 준비한 뒤 XiCAD INS를 실행합니다.',
        'preflight_layers': ['A-WALL', 'A-INSULATION'],
        'post_checks': ['scan_layers'],
    },
}


def list_workflows() -> list[dict[str, Any]]:
    return list(WORKFLOWS.values())


def get_workflow(name: str) -> dict[str, Any]:
    try:
        return WORKFLOWS[name]
    except KeyError as exc:
        raise ValueError(f'Unknown XiCAD workflow: {name}. Available: {sorted(WORKFLOWS)}') from exc
