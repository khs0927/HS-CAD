from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Any

from src.analysis.entity_loader import read_json, write_json_and_md


def fuse_join_evidence(workspace: str | Path) -> dict[str, Any]:
    """Fuse derived analysis artifacts into an explainable evidence graph.

    This does not declare final truth. It creates nodes and edges that downstream review/reporting
    can inspect. The graph is intentionally JSON-first so it can later be exported to DuckDB/Neo4j.
    """
    base = Path(workspace)
    nodes: dict[str, dict[str, Any]] = {}
    edges: list[dict[str, Any]] = []
    _add_text_role_nodes(base, nodes)
    _add_area_nodes(base, nodes)
    _add_titleblock_nodes(base, nodes)
    _add_table_nodes(base, nodes)
    _add_strtree_edges(base, edges)
    _add_leader_edges(base, edges)
    _add_dimension_edges(base, edges)
    _add_titleblock_edges(base, edges)
    confidence = _score_graph(nodes, edges)
    payload = {
        'backend': 'evidence_join_fusion',
        'schema_version': '0.1',
        'summary': {
            'node_count': len(nodes),
            'edge_count': len(edges),
            'text_node_count': sum(1 for n in nodes.values() if n.get('kind') == 'text'),
            'area_node_count': sum(1 for n in nodes.values() if n.get('kind') == 'area'),
            'table_node_count': sum(1 for n in nodes.values() if n.get('kind') == 'table'),
            'titleblock_node_count': sum(1 for n in nodes.values() if n.get('kind') == 'titleblock'),
            'graph_confidence_proxy': confidence,
        },
        'nodes': list(nodes.values())[:20000],
        'edges': edges[:50000],
        'todo': [
            'Promote this graph to DuckDB/Parquet tables.',
            'Add evidence weights and Dempster-Shafer or weighted fusion for conflicting edges.',
            'Add per-file partitioned evidence graphs.',
            'Feed accepted human corrections back into node/edge confidence.',
        ],
        'warnings': ['evidence graph is a fusion scaffold; not final drawing truth'],
    }
    return write_json_and_md(base, 'EVIDENCE_JOIN_FUSION', payload, _markdown(payload))


def _upsert(nodes: dict[str, dict[str, Any]], node_id: str, **payload: Any) -> None:
    if not node_id:
        return
    row = nodes.setdefault(node_id, {'id': node_id})
    row.update({k: v for k, v in payload.items() if v is not None})


def _add_text_role_nodes(base: Path, nodes: dict[str, dict[str, Any]]) -> None:
    payload = read_json(base / 'TEXT_ROLE_INFERENCE.json')
    for item in payload.get('items') or []:
        nid = f"text:{item.get('target_id') or item.get('source_ref') or len(nodes)}"
        _upsert(nodes, nid, kind='text', text=item.get('text'), role=item.get('role'), confidence=item.get('confidence'), bbox=item.get('bbox'), source='TEXT_ROLE_INFERENCE')


def _add_area_nodes(base: Path, nodes: dict[str, dict[str, Any]]) -> None:
    payload = read_json(base / 'REAL_GEOMETRY_POLYGONIZER.json') or read_json(base / 'AREA_BOUNDARY_INFERENCE.json')
    for idx, area in enumerate(payload.get('polygons') or payload.get('candidates') or []):
        aid = area.get('polygon_id') or area.get('entity_id') or f'area:{idx}'
        _upsert(nodes, f'area:{aid}', kind='area', bbox=area.get('bbox'), confidence=area.get('confidence'), area=area.get('area'), source=payload.get('backend'))


def _add_titleblock_nodes(base: Path, nodes: dict[str, dict[str, Any]]) -> None:
    payload = read_json(base / 'TITLEBLOCK_CLASSIFIER.json')
    for idx, cand in enumerate(payload.get('candidates') or []):
        tid = cand.get('titleblock_id') or f'titleblock:{idx}'
        _upsert(nodes, f'titleblock:{tid}', kind='titleblock', confidence=cand.get('confidence'), source=cand.get('source'), reason=cand.get('reason'))


def _add_table_nodes(base: Path, nodes: dict[str, dict[str, Any]]) -> None:
    payload = read_json(base / 'TABLE_CELL_EXTRACTOR.json')
    table_ids = sorted({str(cell.get('table_id')) for cell in payload.get('cells') or [] if cell.get('table_id')})
    for table_id in table_ids:
        _upsert(nodes, f'table:{table_id}', kind='table', source='TABLE_CELL_EXTRACTOR')


def _add_strtree_edges(base: Path, edges: list[dict[str, Any]]) -> None:
    payload = read_json(base / 'STRTREE_SPATIAL_JOIN.json')
    for join in payload.get('joins') or []:
        edges.append({
            'from': f"text:{join.get('text_id')}",
            'to': f"area:{join.get('area_id')}",
            'kind': 'TEXT_IN_AREA',
            'confidence': join.get('confidence', 0.55),
            'source': 'STRTREE_SPATIAL_JOIN',
            'evidence': join,
        })


def _add_leader_edges(base: Path, edges: list[dict[str, Any]]) -> None:
    payload = read_json(base / 'LEADER_GRAPH.json')
    for edge in payload.get('edges') or []:
        edges.append({'from': f"text:{edge.get('from')}", 'to': f"leader:{edge.get('to')}", 'kind': 'TEXT_NEAR_LEADER', 'confidence': edge.get('confidence'), 'source': 'LEADER_GRAPH', 'evidence': edge})


def _add_dimension_edges(base: Path, edges: list[dict[str, Any]]) -> None:
    payload = read_json(base / 'DIMENSION_GRAPH.json')
    for edge in payload.get('edges') or []:
        edges.append({'from': f"text:{edge.get('from')}", 'to': f"dimension_line:{edge.get('to')}", 'kind': 'TEXT_NEAR_DIMENSION_LINE', 'confidence': edge.get('confidence'), 'source': 'DIMENSION_GRAPH', 'evidence': edge})


def _add_titleblock_edges(base: Path, edges: list[dict[str, Any]]) -> None:
    payload = read_json(base / 'TITLEBLOCK_KEY_VALUES.json')
    for row in payload.get('key_values') or []:
        if row.get('key_text'):
            edges.append({'from': f"text:{row.get('source_text_id')}", 'to': f"titleblock_field:{row.get('field')}", 'kind': 'TITLEBLOCK_KEY_VALUE', 'confidence': row.get('confidence'), 'source': 'TITLEBLOCK_KEY_VALUES', 'evidence': row})


def _score_graph(nodes: dict[str, dict[str, Any]], edges: list[dict[str, Any]]) -> float:
    if not nodes:
        return 0.0
    edge_factor = min(0.4, len(edges) / max(len(nodes), 1) * 0.1)
    confidence_values = [float(e.get('confidence') or 0) for e in edges if e.get('confidence') is not None]
    avg_edge = sum(confidence_values) / len(confidence_values) if confidence_values else 0.0
    return round(min(1.0, 0.2 + edge_factor + 0.4 * avg_edge), 6)


def _markdown(payload: dict[str, Any]) -> str:
    s = payload.get('summary') or {}
    return '\n'.join([
        '# Evidence Join Fusion',
        '',
        f"- Nodes: `{s.get('node_count')}`",
        f"- Edges: `{s.get('edge_count')}`",
        f"- Text nodes: `{s.get('text_node_count')}`",
        f"- Area nodes: `{s.get('area_node_count')}`",
        f"- Table nodes: `{s.get('table_node_count')}`",
        f"- Titleblock nodes: `{s.get('titleblock_node_count')}`",
        f"- Graph confidence proxy: `{s.get('graph_confidence_proxy')}`",
        '',
    ])
