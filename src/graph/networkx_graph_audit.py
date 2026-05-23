from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from typing import Any


class NetworkXGraphAuditor:
    backend_id = 'networkx_graph_audit'

    def is_available(self) -> tuple[bool, str]:
        if importlib.util.find_spec('networkx') is None:
            return False, 'networkx not installed'
        return True, 'networkx installed'

    def audit_graph_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        available, reason = self.is_available()
        if not available:
            return {
                'backend': self.backend_id,
                'status': 'unavailable',
                'reason': reason,
                'node_count': 0,
                'edge_count': 0,
                'finding_count': 0,
                'findings': [],
                'metrics': {},
            }
        import networkx as nx

        nodes = _nodes(payload)
        edges = _edges(payload)
        graph = nx.DiGraph()
        for node in nodes:
            graph.add_node(_node_id(node), **node)
        for edge in edges:
            source = _edge_source(edge)
            target = _edge_target(edge)
            if source and target:
                graph.add_edge(source, target, **edge)
        findings = []
        findings.extend(_audit_unlabeled_areas(graph))
        findings.extend(_audit_isolated_text(graph))
        findings.extend(_audit_orphan_layers(graph))
        findings.extend(_audit_file_without_area(graph))
        findings.extend(_audit_disconnected_components(graph))
        findings.extend(_audit_duplicate_label_candidates(graph))
        findings.extend(_audit_layer_semantic_conflict(graph))
        metrics = _metrics(graph, findings)
        return {
            'backend': self.backend_id,
            'status': 'ok',
            'reason': reason,
            'node_count': graph.number_of_nodes(),
            'edge_count': graph.number_of_edges(),
            'finding_count': len(findings),
            'findings': findings,
            'metrics': metrics,
        }

    def audit_file(self, graph_path: str | Path) -> dict[str, Any]:
        source = Path(graph_path)
        if not source.exists():
            return {
                'backend': self.backend_id,
                'status': 'missing_input',
                'reason': f'SPATIAL_GRAPH.json not found: {source}',
                'node_count': 0,
                'edge_count': 0,
                'finding_count': 0,
                'findings': [],
                'metrics': {},
            }
        payload = json.loads(source.read_text(encoding='utf-8'))
        result = self.audit_graph_payload(payload)
        result['source_graph'] = str(source)
        return result


def write_graph_audit(workspace: str | Path, *, out_json: str | Path | None = None, out_md: str | Path | None = None) -> dict[str, Any]:
    base = Path(workspace)
    result = NetworkXGraphAuditor().audit_file(base / 'SPATIAL_GRAPH.json')
    json_path = Path(out_json) if out_json else base / 'GRAPH_AUDIT.json'
    md_path = Path(out_md) if out_md else base / 'GRAPH_AUDIT.md'
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    md_path.write_text(_markdown(result), encoding='utf-8')
    return result


def _nodes(payload: dict[str, Any]) -> list[dict[str, Any]]:
    raw = payload.get('nodes') or []
    if isinstance(raw, dict):
        return [dict(value, id=key) if isinstance(value, dict) else {'id': key} for key, value in raw.items()]
    return [dict(item) for item in raw if isinstance(item, dict)]


def _edges(payload: dict[str, Any]) -> list[dict[str, Any]]:
    raw = payload.get('edges') or []
    return [dict(item) for item in raw if isinstance(item, dict)]


def _node_id(node: dict[str, Any]) -> str:
    return str(node.get('id') or node.get('node_id') or node.get('key') or '')


def _node_kind(node_data: dict[str, Any]) -> str:
    return str(node_data.get('kind') or node_data.get('type') or '')


def _edge_relation(edge_data: dict[str, Any]) -> str:
    return str(edge_data.get('relation') or edge_data.get('type') or edge_data.get('label') or '')


def _edge_source(edge: dict[str, Any]) -> str:
    return str(edge.get('source') or edge.get('from') or edge.get('src') or '')


def _edge_target(edge: dict[str, Any]) -> str:
    return str(edge.get('target') or edge.get('to') or edge.get('dst') or '')


def _audit_unlabeled_areas(graph: Any) -> list[dict[str, Any]]:
    rows = []
    for node, data in graph.nodes(data=True):
        if _node_kind(data) != 'area':
            continue
        has_label = any(_edge_relation(edge_data) == 'HAS_LABEL' for _, _, edge_data in graph.out_edges(node, data=True))
        if not has_label:
            rows.append(_finding('unlabeled_area', 'medium', node, 'Area node has no HAS_LABEL edge.'))
    return rows


def _audit_isolated_text(graph: Any) -> list[dict[str, Any]]:
    rows = []
    for node, data in graph.nodes(data=True):
        if _node_kind(data) == 'text' and graph.degree(node) == 0:
            rows.append(_finding('isolated_text', 'medium', node, 'Text node has no graph relationships.'))
    return rows


def _audit_orphan_layers(graph: Any) -> list[dict[str, Any]]:
    rows = []
    for node, data in graph.nodes(data=True):
        if _node_kind(data) != 'layer':
            continue
        has_any = graph.degree(node) > 0
        if not has_any:
            rows.append(_finding('orphan_layer', 'low', node, 'Layer node has no relationships.'))
    return rows


def _audit_file_without_area(graph: Any) -> list[dict[str, Any]]:
    rows = []
    for node, data in graph.nodes(data=True):
        if _node_kind(data) != 'file':
            continue
        has_area = any(_edge_relation(edge_data) == 'HAS_AREA' for _, _, edge_data in graph.out_edges(node, data=True))
        if not has_area:
            rows.append(_finding('file_without_area', 'medium', node, 'File node has no HAS_AREA edge.'))
    return rows


def _audit_disconnected_components(graph: Any) -> list[dict[str, Any]]:
    import networkx as nx

    rows = []
    undirected = graph.to_undirected()
    components = list(nx.connected_components(undirected))
    for index, component in enumerate(components):
        if index == 0:
            continue
        if len(component) <= 1:
            continue
        rows.append({
            'type': 'disconnected_component',
            'severity': 'low',
            'node_id': None,
            'message': f'Graph contains disconnected component with {len(component)} node(s).',
            'evidence': [f'component_index={index}', f'node_count={len(component)}'],
        })
    return rows


def _audit_duplicate_label_candidates(graph: Any) -> list[dict[str, Any]]:
    rows = []
    for node, data in graph.nodes(data=True):
        if _node_kind(data) != 'area':
            continue
        labels = [target for _, target, edge_data in graph.out_edges(node, data=True) if _edge_relation(edge_data) == 'HAS_LABEL']
        if len(labels) > 1:
            rows.append({
                'type': 'duplicate_label_candidates',
                'severity': 'medium',
                'node_id': node,
                'message': 'Area node has multiple HAS_LABEL candidates.',
                'evidence': [f'label_count={len(labels)}'],
            })
    return rows


def _audit_layer_semantic_conflict(graph: Any) -> list[dict[str, Any]]:
    rows = []
    for node, data in graph.nodes(data=True):
        if _node_kind(data) != 'layer':
            continue
        semantic = str(data.get('predicted_semantic') or data.get('semantic') or '')
        if semantic == 'text_note':
            has_area = any(_edge_relation(edge_data) == 'LAYER_HAS_AREA' for _, _, edge_data in graph.out_edges(node, data=True))
            if has_area:
                rows.append(_finding('layer_semantic_conflict', 'medium', node, 'Text-like layer has area relationships.'))
    return rows


def _metrics(graph: Any, findings: list[dict[str, Any]]) -> dict[str, Any]:
    node_count = graph.number_of_nodes()
    severity_counts: dict[str, int] = {}
    type_counts: dict[str, int] = {}
    kind_counts: dict[str, int] = {}
    for _, data in graph.nodes(data=True):
        kind = _node_kind(data) or 'unknown'
        kind_counts[kind] = kind_counts.get(kind, 0) + 1
    for finding in findings:
        severity = str(finding.get('severity') or 'unknown')
        ftype = str(finding.get('type') or 'unknown')
        severity_counts[severity] = severity_counts.get(severity, 0) + 1
        type_counts[ftype] = type_counts.get(ftype, 0) + 1
    return {
        'kind_counts': kind_counts,
        'severity_counts': severity_counts,
        'finding_type_counts': type_counts,
        'finding_rate': round(len(findings) / node_count, 6) if node_count else 0.0,
    }


def _finding(ftype: str, severity: str, node_id: str, message: str) -> dict[str, Any]:
    return {
        'type': ftype,
        'severity': severity,
        'node_id': node_id,
        'message': message,
        'evidence': [],
    }


def _markdown(result: dict[str, Any]) -> str:
    lines = [
        '# Graph Audit',
        '',
        f"- Backend: `{result.get('backend')}`",
        f"- Status: `{result.get('status')}`",
        f"- Nodes: `{result.get('node_count')}`",
        f"- Edges: `{result.get('edge_count')}`",
        f"- Findings: `{result.get('finding_count')}`",
        '',
        '## Findings',
        '',
    ]
    for finding in result.get('findings') or []:
        lines.append(f"- **{finding.get('type')}** `{finding.get('severity')}`: {finding.get('message')} ({finding.get('node_id')})")
    if not result.get('findings'):
        lines.append('- No findings.')
    lines.append('')
    return '\n'.join(lines)
