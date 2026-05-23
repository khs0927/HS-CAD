from __future__ import annotations

import json
from pathlib import Path

import typer

from src.analysis.cross_validation import CrossValidationScorer
from src.app.cli import app
from src.app.logger import console, success


@app.command('hscad-cross-validate')
def hscad_cross_validate(
    workspace: Path = typer.Option(..., '--workspace', '-w'),
    out_json: Path | None = typer.Option(None, '--out-json'),
):
    results = []
    scorer = CrossValidationScorer()
    area_path = workspace / 'AREA_ELEMENTS.json'
    text_path = workspace / 'TEXT_ROLE_INFERENCE.json'
    layer_path = workspace / 'LAYER_SEMANTICS.json'
    graph_path = workspace / 'SPATIAL_GRAPH.json'

    if area_path.exists():
        areas = json.loads(area_path.read_text(encoding='utf-8'))
        for area in areas.get('areas') or []:
            results.append(scorer.score('area_element', _area_id(area), _area_signals(area)))
    if text_path.exists():
        texts = json.loads(text_path.read_text(encoding='utf-8'))
        for role in texts.get('roles') or []:
            results.append(scorer.score('text_role', _text_id(role), _text_signals(role)))
    if layer_path.exists():
        layers = json.loads(layer_path.read_text(encoding='utf-8'))
        for layer in layers.get('layers') or []:
            results.append(scorer.score('layer_semantic', _layer_id(layer), _layer_signals(layer)))
    if graph_path.exists():
        graph = json.loads(graph_path.read_text(encoding='utf-8'))
        results.append(scorer.score('graph_relationship', 'graph:workspace', _graph_signals(graph)))

    payload = {
        'workspace': str(workspace),
        'result_count': len(results),
        'avg_agreement_score': round(sum(float(item.get('agreement_score') or 0) for item in results) / len(results), 6) if results else 0.0,
        'avg_confidence': round(sum(float(item.get('confidence') or 0) for item in results) / len(results), 6) if results else 0.0,
        'results': results,
    }
    json_path = out_json or workspace / 'CROSS_VALIDATION.json'
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
    console.print({'json': str(json_path), 'result_count': payload['result_count'], 'avg_confidence': payload['avg_confidence']})
    success('Cross-validation summary written')


def _area_id(area: dict) -> str:
    return f"area:{area.get('file_id')}:{area.get('handle') or area.get('label') or 'unknown'}"


def _text_id(role: dict) -> str:
    return f"text:{role.get('file_id')}:{role.get('handle') or role.get('text') or 'unknown'}"


def _layer_id(layer: dict) -> str:
    return f"layer:{layer.get('layer') or 'unknown'}"


def _area_signals(area: dict) -> dict[str, dict]:
    signals: dict[str, dict] = {}
    source = area.get('source_type')
    if source == 'closed_polyline':
        signals['closed_polyline_area'] = {'score': 1.0, 'evidence': area.get('evidence') or []}
    if source == 'line_loop':
        signals['line_loop_area'] = {'score': 1.0, 'evidence': area.get('evidence') or []}
    if source == 'segment_loop':
        signals['arc_segment_loop_area'] = {'score': 1.0, 'evidence': area.get('evidence') or []}
    if source == 'hatch_boundary':
        signals['hatch_boundary_area'] = {'score': 1.0, 'evidence': area.get('evidence') or []}
    if area.get('label'):
        signals['room_label_inside'] = {'score': float(area.get('confidence') or 0.7), 'evidence': ['area has label']}
    return signals


def _text_signals(role: dict) -> dict[str, dict]:
    signals = {'cad_text_position': {'score': 1.0, 'evidence': ['CAD text entity exists']}}
    evidence = role.get('evidence') or []
    joined = ' '.join(evidence)
    if 'inside' in joined:
        signals['boundary_containment'] = {'score': float(role.get('confidence') or 0.7), 'evidence': evidence}
    if role.get('role') == 'table_cell_text':
        signals['table_region_exclusion'] = {'score': 0.5, 'evidence': evidence}
    if role.get('role') == 'leader_note':
        signals['leader_proximity'] = {'score': float(role.get('confidence') or 0.7), 'evidence': evidence}
    if role.get('layer'):
        signals['layer_semantic_support'] = {'score': 0.6, 'evidence': [f"layer={role.get('layer')}"]}
    return signals


def _layer_signals(layer: dict) -> dict[str, dict]:
    signals = {}
    evidence = layer.get('evidence') or []
    counts = layer.get('counts') or {}
    if any('layer name' in item for item in evidence):
        signals['layer_name_pattern'] = {'score': float(layer.get('confidence') or 0.6), 'evidence': evidence}
    if counts.get('entity_types'):
        signals['entity_type_distribution'] = {'score': 0.8, 'evidence': ['entity type distribution available']}
    if counts.get('colors'):
        signals['color_distribution'] = {'score': 0.6, 'evidence': ['color distribution available']}
    if counts.get('linetypes'):
        signals['linetype_distribution'] = {'score': 0.6, 'evidence': ['linetype distribution available']}
    if counts.get('sample_blocks'):
        signals['block_name_samples'] = {'score': 0.7, 'evidence': ['block samples available']}
    return signals


def _graph_signals(graph: dict) -> dict[str, dict]:
    counts = graph.get('edge_relation_counts') or {}
    signals = {}
    if counts.get('HAS_LABEL', 0):
        signals['area_has_label'] = {'score': 0.8, 'evidence': [f"HAS_LABEL={counts.get('HAS_LABEL')}"]}
    if counts.get('LAYER_HAS_TEXT', 0):
        signals['layer_has_text'] = {'score': 0.8, 'evidence': [f"LAYER_HAS_TEXT={counts.get('LAYER_HAS_TEXT')}"]}
    if counts.get('LAYER_HAS_AREA', 0):
        signals['layer_has_area'] = {'score': 0.8, 'evidence': [f"LAYER_HAS_AREA={counts.get('LAYER_HAS_AREA')}"]}
    return signals
