from __future__ import annotations

import importlib.util
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from src.spatial.area_elements import AreaElementInferer
from src.spatial.text_roles import TextRoleInferer


@dataclass
class GraphNode:
    id: str
    kind: str
    label: str | None = None
    properties: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class GraphEdge:
    source: str
    target: str
    relation: str
    confidence: float = 1.0
    evidence: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class SpatialGraphExporter:
    """Export deterministic JSON graph from inferred area and text artifacts.

    The JSON graph is the stable contract. NetworkX can be used later as an
    optional analysis backend, but is not required to generate the graph.
    """

    def __init__(self, *, area_backend: str = 'auto'):
        self.area_backend = area_backend

    def export_record(self, record: dict[str, Any]) -> dict[str, Any]:
        file_id = str(record.get('file_id') or '')
        text_result = TextRoleInferer().infer_record(record)
        area_result = AreaElementInferer(backend=self.area_backend).infer_record(record)
        nodes: dict[str, GraphNode] = {}
        edges: list[GraphEdge] = []

        file_node = GraphNode(id=f'file:{file_id}', kind='file', label=str(record.get('relative_path') or file_id), properties={'file_id': file_id})
        nodes[file_node.id] = file_node

        for role in text_result.get('roles') or []:
            text_id = self._text_node_id(file_id, role)
            nodes[text_id] = GraphNode(
                id=text_id,
                kind='text',
                label=role.get('text'),
                properties={
                    'role': role.get('role'),
                    'confidence': role.get('confidence'),
                    'layer': role.get('layer'),
                    'handle': role.get('handle'),
                    'insert': role.get('insert'),
                    'evidence': role.get('evidence') or [],
                },
            )
            edges.append(GraphEdge(source=file_node.id, target=text_id, relation='HAS_TEXT', confidence=float(role.get('confidence') or 0.0)))

        for area in area_result.get('areas') or []:
            area_id = self._area_node_id(file_id, area)
            nodes[area_id] = GraphNode(
                id=area_id,
                kind='area',
                label=area.get('label'),
                properties={
                    'area': area.get('area'),
                    'source_type': area.get('source_type'),
                    'layer': area.get('layer'),
                    'confidence': area.get('confidence'),
                    'bbox': area.get('bbox'),
                    'handle': area.get('handle'),
                    'evidence': area.get('evidence') or [],
                },
            )
            edges.append(GraphEdge(source=file_node.id, target=area_id, relation='HAS_AREA', confidence=float(area.get('confidence') or 0.0), evidence=area.get('evidence') or []))
            label_handle = area.get('label_handle')
            if label_handle:
                text_id = self._text_node_id(file_id, {'handle': label_handle, 'text': area.get('label')})
                if text_id in nodes:
                    edges.append(GraphEdge(
                        source=area_id,
                        target=text_id,
                        relation='HAS_LABEL',
                        confidence=float(area.get('confidence') or 0.0),
                        evidence=['area label_handle matched text role node'] + list(area.get('evidence') or []),
                    ))

        return {
            'file_id': file_id,
            'relative_path': record.get('relative_path'),
            'node_count': len(nodes),
            'edge_count': len(edges),
            'nodes': [node.to_dict() for node in nodes.values()],
            'edges': [edge.to_dict() for edge in edges],
            'backends': {
                'area_backend': area_result.get('backend'),
                'networkx_available': self.networkx_available(),
            },
        }

    def export_json_file(self, path: str | Path) -> dict[str, Any]:
        source = Path(path)
        record = json.loads(source.read_text(encoding='utf-8'))
        result = self.export_record(record)
        result['source_json'] = str(source)
        return result

    def export_json_dir(self, json_dir: str | Path) -> dict[str, Any]:
        base = Path(json_dir)
        files = [self.export_json_file(path) for path in sorted(base.glob('*.json'))]
        nodes: list[dict[str, Any]] = []
        edges: list[dict[str, Any]] = []
        for file_result in files:
            nodes.extend(file_result.get('nodes') or [])
            edges.extend(file_result.get('edges') or [])
        node_kind_counts: dict[str, int] = {}
        edge_relation_counts: dict[str, int] = {}
        for node in nodes:
            node_kind_counts[node['kind']] = node_kind_counts.get(node['kind'], 0) + 1
        for edge in edges:
            edge_relation_counts[edge['relation']] = edge_relation_counts.get(edge['relation'], 0) + 1
        return {
            'json_dir': str(base),
            'file_count': len(files),
            'node_count': len(nodes),
            'edge_count': len(edges),
            'node_kind_counts': node_kind_counts,
            'edge_relation_counts': edge_relation_counts,
            'files': files,
            'nodes': nodes,
            'edges': edges,
            'backends': {
                'area_backend': self.area_backend,
                'networkx_available': self.networkx_available(),
            },
        }

    @staticmethod
    def networkx_available() -> bool:
        return importlib.util.find_spec('networkx') is not None

    @staticmethod
    def _text_node_id(file_id: str, role: dict[str, Any]) -> str:
        handle = role.get('handle') or f"text-{abs(hash(role.get('text')))}"
        return f'text:{file_id}:{handle}'

    @staticmethod
    def _area_node_id(file_id: str, area: dict[str, Any]) -> str:
        handle = area.get('handle') or f"area-{abs(hash(json.dumps(area.get('bbox'), ensure_ascii=False)))}"
        return f'area:{file_id}:{handle}'
