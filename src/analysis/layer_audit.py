from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from src.analysis.layer_semantics import LayerSemanticInferer


class LayerSemanticsAuditor:
    """Create review/audit findings from vendor-neutral layer semantic guesses.

    This does not create company-specific mappings. It only identifies layers
    that need manual review or future calibration against the real corpus.
    """

    def __init__(self, *, low_confidence_threshold: float = 0.55):
        self.low_confidence_threshold = low_confidence_threshold

    def audit_result(self, result: dict[str, Any]) -> dict[str, Any]:
        findings: list[dict[str, Any]] = []
        semantic_counts = Counter()
        for layer in result.get('layers') or []:
            semantic = str(layer.get('predicted_semantic') or 'unknown')
            semantic_counts[semantic] += 1
            confidence = float(layer.get('confidence') or 0.0)
            counts = layer.get('counts') or {}
            entity_types = counts.get('entity_types') or {}
            evidence = list(layer.get('evidence') or [])
            if semantic == 'unknown':
                findings.append(_finding('unknown_layer_semantic', layer, 'Layer semantic could not be inferred.', 'medium'))
            if confidence < self.low_confidence_threshold:
                findings.append(_finding('low_confidence_layer_semantic', layer, f'Confidence {confidence} is below threshold {self.low_confidence_threshold}.', 'medium'))
            if _has_mixed_heavy_signals(entity_types):
                findings.append(_finding('mixed_entity_type_layer', layer, 'Layer contains mixed heavy entity type signals and may need manual review.', 'low'))
            if semantic == 'text_note' and entity_types.get('LINE', 0) + entity_types.get('POLYLINE', 0) > entity_types.get('TEXT', 0) + entity_types.get('MTEXT', 0):
                findings.append(_finding('text_layer_with_linework', layer, 'Text-like layer also contains significant linework.', 'low'))
            if semantic in {'wall', 'door', 'window', 'column'} and not evidence:
                findings.append(_finding('semantic_without_evidence', layer, 'Structural/architectural semantic has no explicit evidence.', 'medium'))
        severity_counts = Counter(item['severity'] for item in findings)
        type_counts = Counter(item['type'] for item in findings)
        return {
            'source_json_dir': result.get('json_dir'),
            'file_count': result.get('file_count'),
            'layer_count': result.get('layer_count'),
            'semantic_counts': dict(semantic_counts),
            'finding_count': len(findings),
            'finding_type_counts': dict(type_counts),
            'severity_counts': dict(severity_counts),
            'findings': findings,
            'calibration_todo': {
                'company_specific_mapping_deferred': True,
                'recommended_next_step': 'Review low-confidence and unknown layers against real Webhard drawings before adding company profile overrides.',
            },
        }

    def audit_json_dir(self, json_dir: str | Path) -> dict[str, Any]:
        result = LayerSemanticInferer().infer_json_dir(json_dir)
        return self.audit_result(result)


def write_layer_audit(workspace: str | Path, *, out_json: str | Path | None = None, out_md: str | Path | None = None) -> dict[str, Any]:
    base = Path(workspace)
    result = LayerSemanticsAuditor().audit_json_dir(base / 'fileized' / 'json')
    json_path = Path(out_json) if out_json else base / 'LAYER_AUDIT.json'
    md_path = Path(out_md) if out_md else base / 'LAYER_AUDIT.md'
    json_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    md_path.write_text(layer_audit_markdown(result), encoding='utf-8')
    return result


def layer_audit_markdown(result: dict[str, Any]) -> str:
    lines = [
        '# HS-CAD Layer Semantics Audit',
        '',
        f'- Files: {result.get("file_count")}',
        f'- Layers: {result.get("layer_count")}',
        f'- Findings: {result.get("finding_count")}',
        f'- Severity counts: `{json.dumps(result.get("severity_counts", {}), ensure_ascii=False)}`',
        f'- Finding type counts: `{json.dumps(result.get("finding_type_counts", {}), ensure_ascii=False)}`',
        '',
        '## Calibration TODO',
        '',
        '- Company-specific layer mapping is intentionally deferred.',
        '- Review findings against actual Webhard drawings before adding company profile overrides.',
        '',
        '## Findings',
        '',
        '| Severity | Type | Layer | Semantic | Confidence | Message |',
        '|---|---|---|---|---:|---|',
    ]
    for item in result.get('findings', [])[:500]:
        layer = item.get('layer') or {}
        lines.append(
            f"| `{_escape(item.get('severity'))}` | `{_escape(item.get('type'))}` | `{_escape(layer.get('layer'))}` | "
            f"`{_escape(layer.get('predicted_semantic'))}` | {layer.get('confidence')} | {_escape(item.get('message'))} |"
        )
    return '\n'.join(lines) + '\n'


def _finding(kind: str, layer: dict[str, Any], message: str, severity: str) -> dict[str, Any]:
    return {
        'type': kind,
        'severity': severity,
        'message': message,
        'layer': {
            'layer': layer.get('layer'),
            'predicted_semantic': layer.get('predicted_semantic'),
            'confidence': layer.get('confidence'),
            'evidence': layer.get('evidence') or [],
            'counts': layer.get('counts') or {},
        },
    }


def _has_mixed_heavy_signals(entity_types: dict[str, Any]) -> bool:
    heavy = 0
    for key in ['LINE', 'POLYLINE', 'TEXT', 'MTEXT', 'INSERT', 'DIMENSION', 'HATCH']:
        if int(entity_types.get(key, 0) or 0) >= 5:
            heavy += 1
    return heavy >= 3


def _escape(value: object) -> str:
    return str(value or '').replace('|', '\\|').replace('\n', ' ')
