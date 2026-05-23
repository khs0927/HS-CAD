from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class LayerSemanticGuess:
    layer: str
    predicted_semantic: str
    confidence: float
    evidence: list[str] = field(default_factory=list)
    counts: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class LayerSemanticInferer:
    """Infer practical CAD layer semantics from fileized entities.

    This is vendor-neutral and company-profile-friendly. It uses layer names,
    entity type distributions, text/block signals, color, and linetype evidence.
    """

    def infer_record(self, record: dict[str, Any]) -> dict[str, Any]:
        file_id = str(record.get('file_id') or '')
        rows = self._layer_stats(record.get('entities') or [])
        guesses = [self._guess(layer, stats) for layer, stats in sorted(rows.items())]
        counts = Counter(item.predicted_semantic for item in guesses)
        return {
            'file_id': file_id,
            'relative_path': record.get('relative_path'),
            'layer_count': len(guesses),
            'semantic_counts': dict(counts),
            'layers': [item.to_dict() for item in guesses],
        }

    def infer_json_file(self, path: str | Path) -> dict[str, Any]:
        source = Path(path)
        record = json.loads(source.read_text(encoding='utf-8'))
        result = self.infer_record(record)
        result['source_json'] = str(source)
        return result

    def infer_json_dir(self, json_dir: str | Path) -> dict[str, Any]:
        base = Path(json_dir)
        files = [self.infer_json_file(path) for path in sorted(base.glob('*.json'))]
        merged: dict[str, dict[str, Any]] = {}
        for file_result in files:
            for layer in file_result.get('layers') or []:
                name = layer['layer']
                target = merged.setdefault(name, {'layer': name, 'entity_types': Counter(), 'colors': Counter(), 'linetypes': Counter(), 'texts': [], 'blocks': []})
                counts = layer.get('counts') or {}
                target['entity_types'].update(counts.get('entity_types') or {})
                target['colors'].update(counts.get('colors') or {})
                target['linetypes'].update(counts.get('linetypes') or {})
                target['texts'].extend((counts.get('sample_texts') or [])[:20])
                target['blocks'].extend((counts.get('sample_blocks') or [])[:20])
        guesses: list[LayerSemanticGuess] = []
        for name, stats in sorted(merged.items()):
            normalized_stats = {
                'entity_types': dict(stats['entity_types']),
                'colors': dict(stats['colors']),
                'linetypes': dict(stats['linetypes']),
                'sample_texts': stats['texts'][:20],
                'sample_blocks': stats['blocks'][:20],
            }
            guesses.append(self._guess(name, normalized_stats))
        semantic_counts = Counter(item.predicted_semantic for item in guesses)
        return {
            'json_dir': str(base),
            'file_count': len(files),
            'layer_count': len(guesses),
            'semantic_counts': dict(semantic_counts),
            'layers': [item.to_dict() for item in guesses],
        }

    @staticmethod
    def _layer_stats(entities: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
        rows: dict[str, dict[str, Any]] = defaultdict(lambda: {'entity_types': Counter(), 'colors': Counter(), 'linetypes': Counter(), 'sample_texts': [], 'sample_blocks': []})
        for entity in entities:
            layer = str(entity.get('layer') or 'UNKNOWN')
            stats = rows[layer]
            stats['entity_types'][str(entity.get('entity_type') or 'UNKNOWN').upper()] += 1
            if entity.get('color') is not None:
                stats['colors'][str(entity.get('color'))] += 1
            if entity.get('linetype') is not None:
                stats['linetypes'][str(entity.get('linetype'))] += 1
            if entity.get('text') and len(stats['sample_texts']) < 20:
                stats['sample_texts'].append(str(entity.get('text')))
            block_name = entity.get('effective_name') or entity.get('name')
            if block_name and len(stats['sample_blocks']) < 20:
                stats['sample_blocks'].append(str(block_name))
        return {
            name: {
                'entity_types': dict(stats['entity_types']),
                'colors': dict(stats['colors']),
                'linetypes': dict(stats['linetypes']),
                'sample_texts': stats['sample_texts'],
                'sample_blocks': stats['sample_blocks'],
            }
            for name, stats in rows.items()
        }

    def _guess(self, layer: str, stats: dict[str, Any]) -> LayerSemanticGuess:
        name = _norm(layer)
        entity_types = Counter(stats.get('entity_types') or {})
        texts = ' '.join(stats.get('sample_texts') or [])
        blocks = ' '.join(stats.get('sample_blocks') or [])
        evidence: list[str] = []
        scores = Counter()

        for semantic, patterns in NAME_PATTERNS.items():
            if any(re.search(pattern, name) for pattern in patterns):
                scores[semantic] += 5
                evidence.append(f'layer name matches {semantic}')

        if entity_types['DIMENSION']:
            scores['dimension'] += 4
            evidence.append('contains DIMENSION entities')
        if entity_types['TEXT'] + entity_types['MTEXT'] > max(3, sum(entity_types.values()) * 0.5):
            scores['text_note'] += 3
            evidence.append('text-heavy layer')
        if entity_types['HATCH']:
            scores['hatch_area'] += 3
            evidence.append('contains HATCH entities')
        if entity_types['INSERT']:
            scores['block_symbol'] += 2
            evidence.append('contains INSERT/block entities')
        if entity_types['LINE'] + entity_types['POLYLINE'] > 10:
            scores['linework'] += 1
            evidence.append('linework-heavy layer')
        if _contains_any(texts, ['방화문', '도어', '문', 'DOOR']):
            scores['door'] += 2
            evidence.append('sample text suggests door')
        if _contains_any(blocks, ['DOOR', 'DR', 'WINDOW', 'WIN', 'COL', 'COLUMN']):
            scores['block_symbol'] += 2
            evidence.append('sample block names suggest symbols')

        if not scores:
            semantic = 'unknown'
            confidence = 0.2
            evidence.append('no strong semantic signal')
        else:
            semantic, score = scores.most_common(1)[0]
            confidence = min(0.95, 0.25 + score * 0.1)
        return LayerSemanticGuess(
            layer=layer,
            predicted_semantic=semantic,
            confidence=round(confidence, 3),
            evidence=evidence[:8],
            counts=stats,
        )


NAME_PATTERNS = {
    'wall': [r'(?:^|_)WALL(?:_|$)', r'(?:^|_)WAL\d*(?:_|$)', r'벽', r'벽체'],
    'door': [r'\bDOOR\b', r'\bDR\b', r'문'],
    'window': [r'\bWIN\b', r'\bWINDOW\b', r'창'],
    'column': [r'\bCOL\b', r'COLUMN', r'기둥'],
    'beam': [r'\bBEAM\b', r'\bBM\b', r'보'],
    'grid': [r'\bGRID\b', r'\bCEN\b', r'중심', r'축선'],
    'dimension': [r'\bDIM\b', r'치수'],
    'text_note': [r'\bTEXT\b', r'\bNOTE\b', r'주기', r'문자'],
    'hatch_area': [r'\bHATCH\b', r'해치', r'마감'],
    'furniture': [r'FURN', r'가구'],
    'equipment': [r'EQPM', r'EQUIP', r'설비'],
    'plumbing': [r'PLUMB', r'위생', r'배관'],
    'electrical': [r'ELEC', r'전기'],
    'fire': [r'FIRE', r'소방'],
}


def _norm(value: str) -> str:
    return value.upper().replace('-', '_').replace('$', '_')


def _contains_any(value: str, needles: list[str]) -> bool:
    upper = value.upper()
    return any(needle.upper() in upper for needle in needles)
