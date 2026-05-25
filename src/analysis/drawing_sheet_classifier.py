from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.analysis.entity_loader import read_json, write_json_and_md

DISCIPLINE_HINTS = {
    'architectural': ['건축', '평면', '입면', '단면', '창호', '마감', 'architectural', 'floor plan'],
    'structural': ['구조', '철골', '기초', '보', '기둥', 'structural', 'foundation'],
    'electrical': ['전기', '조명', '분전', '배선', 'electrical', 'lighting'],
    'mechanical': ['기계', '공조', '덕트', '배관', 'mechanical', 'duct', 'pipe'],
    'fire': ['소방', '스프링클러', '감지기', 'fire', 'sprinkler'],
    'civil': ['토목', '배치', '대지', '우수', '오수', 'civil', 'site'],
}

SHEET_TYPE_HINTS = {
    'plan': ['평면', 'plan'],
    'section': ['단면', 'section'],
    'elevation': ['입면', 'elevation'],
    'detail': ['상세', 'detail'],
    'schedule': ['일람', 'schedule', '표'],
    'cover': ['표지', '개요', 'cover'],
}


def classify_drawing_sheets(workspace: str | Path) -> dict[str, Any]:
    base = Path(workspace)
    metadata = read_json(base / 'DRAWING_SHEET_METADATA.json')
    title_values = read_json(base / 'TITLEBLOCK_KEY_VALUES.json')
    layer_profile = read_json(base / 'LAYER_PROFILE_SAMPLE.json')
    text_roles = read_json(base / 'TEXT_ROLE_INFERENCE.json')
    text_blob = _collect_text(metadata, title_values, layer_profile, text_roles)
    discipline_scores = _score_hints(text_blob, DISCIPLINE_HINTS)
    sheet_type_scores = _score_hints(text_blob, SHEET_TYPE_HINTS)
    discipline = _best_label(discipline_scores)
    sheet_type = _best_label(sheet_type_scores)
    payload = {
        'backend': 'drawing_sheet_classifier',
        'schema_version': '0.1',
        'summary': {
            'discipline': discipline['label'],
            'discipline_confidence': discipline['confidence'],
            'sheet_type': sheet_type['label'],
            'sheet_type_confidence': sheet_type['confidence'],
        },
        'discipline_scores': discipline_scores,
        'sheet_type_scores': sheet_type_scores,
        'source_text_sample': text_blob[:2000],
        'todo': [
            'Use filename/path metadata from fileized records.',
            'Use titleblock key-value fields when actual values are extracted.',
            'Add layer-profile-based discipline priors after webhard corpus sampling.',
            'Add per-sheet classification instead of workspace-level classification.',
        ],
        'warnings': ['workspace-level weak classifier; not final sheet truth'],
    }
    return write_json_and_md(base, 'DRAWING_SHEET_CLASSIFIER', payload, _markdown(payload))


def _collect_text(*payloads: dict[str, Any]) -> str:
    parts: list[str] = []
    for payload in payloads:
        parts.append(json.dumps(payload, ensure_ascii=False)[:10000])
    return '\n'.join(parts).lower()


def _score_hints(text: str, hints: dict[str, list[str]]) -> dict[str, float]:
    scores: dict[str, float] = {}
    for label, words in hints.items():
        score = 0.0
        for word in words:
            score += text.count(word.lower())
        scores[label] = round(min(1.0, score / 5.0), 6)
    if not any(scores.values()):
        scores['unknown'] = 0.0
    return scores


def _best_label(scores: dict[str, float]) -> dict[str, Any]:
    if not scores:
        return {'label': 'unknown', 'confidence': 0.0}
    label, score = max(scores.items(), key=lambda pair: pair[1])
    if score <= 0:
        return {'label': 'unknown', 'confidence': 0.0}
    return {'label': label, 'confidence': score}


def _markdown(payload: dict[str, Any]) -> str:
    s = payload.get('summary') or {}
    return '\n'.join([
        '# Drawing Sheet Classifier',
        '',
        f"- Discipline: `{s.get('discipline')}` (`{s.get('discipline_confidence')}`)",
        f"- Sheet type: `{s.get('sheet_type')}` (`{s.get('sheet_type_confidence')}`)",
        '',
    ])
