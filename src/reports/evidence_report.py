from __future__ import annotations

from typing import Any


def render_evidence_markdown(package: dict[str, Any]) -> str:
    lines: list[str] = [
        '# HS-CAD Evidence Package',
        '',
        f'- Source: {package.get("source", "unknown")}',
        f'- Object count: {package.get("object_count", 0)}',
        '',
    ]
    _append_counts(lines, 'Object type counts', package.get('object_type_counts') or {})
    _append_counts(lines, 'Layer counts', package.get('layer_counts') or {})
    _append_boundary_summary(lines, package.get('boundary_summary') or {})
    _append_dimension_summary(lines, package.get('dimension_summary') or {})
    return '\n'.join(lines).rstrip() + '\n'


def _append_counts(lines: list[str], title: str, counts: dict[str, Any]) -> None:
    lines += [f'## {title}', '']
    if not counts:
        lines += ['- None', '']
        return
    for key, value in counts.items():
        lines.append(f'- {key}: {value}')
    lines.append('')


def _append_boundary_summary(lines: list[str], summary: dict[str, Any]) -> None:
    lines += ['## Boundary candidates', '']
    lines.append(f'- Candidate count: {summary.get("candidate_count", 0)}')
    lines.append(f'- Total candidate area: {summary.get("total_candidate_area", 0)}')
    for index, item in enumerate((summary.get('candidates') or [])[:20], start=1):
        lines.append(
            f'- #{index}: layer={item.get("layer", "")}, area={item.get("area", 0)}, bbox={item.get("bbox", "")}, confidence={item.get("confidence", "")}'
        )
    lines.append('')


def _append_dimension_summary(lines: list[str], summary: dict[str, Any]) -> None:
    lines += ['## Dimension evidence', '']
    lines.append(f'- Dimension count: {summary.get("dimension_count", 0)}')
    lines.append(f'- Measured count: {summary.get("measured_count", 0)}')
    for kind, count in (summary.get('by_kind') or {}).items():
        lines.append(f'- {kind}: {count}')
    for index, item in enumerate((summary.get('dimensions') or [])[:20], start=1):
        lines.append(
            f'- #{index}: layer={item.get("layer", "")}, kind={item.get("dimension_kind", "")}, value={item.get("value", "")}, text={item.get("text", "")}, confidence={item.get("confidence", "")}'
        )
    lines.append('')
