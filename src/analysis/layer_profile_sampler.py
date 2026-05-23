from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from src.analysis.entity_loader import load_fileized_entities, write_json_and_md


def sample_layer_profiles(workspace: str | Path, *, max_text_samples_per_layer: int = 20) -> dict[str, Any]:
    """Collect layer statistics without hard-coding company-specific mappings.

    This intentionally avoids deciding final semantics. It only produces evidence to help
    future project/company-specific calibration.
    """
    base = Path(workspace)
    entities = load_fileized_entities(base)
    by_layer: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for ent in entities:
        by_layer[str(ent.get('layer') or '<NO_LAYER>')].append(ent)

    profiles = []
    for layer, rows in sorted(by_layer.items(), key=lambda pair: (-len(pair[1]), pair[0])):
        type_counts = Counter(str(r.get('entity_type') or '') for r in rows)
        color_counts = Counter(str(r.get('color') or r.get('aci') or '') for r in rows if r.get('color') is not None or r.get('aci') is not None)
        linetype_counts = Counter(str(r.get('linetype') or '') for r in rows if r.get('linetype'))
        text_samples = []
        for row in rows:
            if row.get('entity_type') in {'TEXT', 'MTEXT'}:
                text = row.get('text') or row.get('value') or row.get('content')
                if text:
                    text_samples.append(str(text)[:120])
            if len(text_samples) >= max_text_samples_per_layer:
                break
        bbox_count = sum(1 for r in rows if isinstance(r.get('bbox'), list) and len(r.get('bbox')) == 4)
        profiles.append({
            'layer': layer,
            'entity_count': len(rows),
            'bbox_count': bbox_count,
            'entity_type_counts': dict(type_counts.most_common(20)),
            'color_counts': dict(color_counts.most_common(10)),
            'linetype_counts': dict(linetype_counts.most_common(10)),
            'text_samples': text_samples,
            'semantic_guess': _weak_semantic_guess(layer, type_counts, text_samples),
            'semantic_guess_confidence': 0.25,
            'status': 'sample_only_not_final_mapping',
        })
    payload = {
        'backend': 'layer_profile_sampler',
        'schema_version': '0.1',
        'summary': {
            'entity_count': len(entities),
            'layer_count': len(profiles),
            'top_layer': profiles[0]['layer'] if profiles else None,
        },
        'profiles': profiles,
        'todo': [
            'Run on real webhard corpus and review layer distributions.',
            'Do not finalize company-specific layer semantics until enough samples are collected.',
            'Add project/company profile IDs later.',
            'Use accepted/corrected text roles as weak labels for layer semantics.',
        ],
        'warnings': ['layer profiles are samples, not final semantics'],
    }
    return write_json_and_md(base, 'LAYER_PROFILE_SAMPLE', payload, _markdown(payload))


def _weak_semantic_guess(layer: str, type_counts: Counter, text_samples: list[str]) -> str:
    l = layer.lower()
    if any(k in l for k in ['wall', 'wal', '벽']):
        return 'wall_candidate'
    if any(k in l for k in ['dim', '치수']):
        return 'dimension_candidate'
    if any(k in l for k in ['text', 'txt', '문자']):
        return 'text_candidate'
    if any(k in l for k in ['door', 'dr', '문']):
        return 'door_candidate'
    if any(k in l for k in ['win', '창']):
        return 'window_candidate'
    if type_counts.get('TEXT', 0) + type_counts.get('MTEXT', 0) > sum(type_counts.values()) * 0.5:
        return 'text_heavy_layer'
    return 'unknown'


def _markdown(payload: dict[str, Any]) -> str:
    s = payload.get('summary') or {}
    lines = [
        '# Layer Profile Sample',
        '',
        f"- Entity count: `{s.get('entity_count')}`",
        f"- Layer count: `{s.get('layer_count')}`",
        f"- Top layer: `{s.get('top_layer')}`",
        '',
        '| Layer | Count | Weak Guess |',
        '|---|---:|---|',
    ]
    for row in (payload.get('profiles') or [])[:50]:
        lines.append(f"| {row.get('layer')} | {row.get('entity_count')} | {row.get('semantic_guess')} |")
    lines.append('')
    return '\n'.join(lines)
