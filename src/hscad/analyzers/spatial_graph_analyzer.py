"""Simple spatial graph builder.

The first implementation creates entity centroids and nearest text links. It is
safe and deterministic, and can later be replaced or enhanced with Shapely.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from hscad.analyzers.geometry_utils import centroid, distance
from hscad.core.evidence import Evidence, make_evidence
from hscad.core.models import DrawingEntity, FileizedDrawing


@dataclass(frozen=True)
class SpatialNode:
    entity_id: str
    entity_type: str
    layer: str
    centroid: tuple[float, float]

    def to_record(self) -> dict[str, Any]:
        return self.__dict__.copy()


@dataclass(frozen=True)
class SpatialEdge:
    from_id: str
    to_id: str
    relation: str
    distance: float

    def to_record(self) -> dict[str, Any]:
        return self.__dict__.copy()


@dataclass(frozen=True)
class SpatialGraphAnalysis:
    nodes: list[SpatialNode]
    edges: list[SpatialEdge]
    evidence: list[Evidence]

    def to_record(self) -> dict[str, Any]:
        return {"nodes": [n.to_record() for n in self.nodes], "edges": [e.to_record() for e in self.edges], "evidence": [e.to_record() for e in self.evidence]}


class SpatialGraphAnalyzer:
    def analyze(self, drawing: FileizedDrawing) -> SpatialGraphAnalysis:
        nodes = [SpatialNode(e.entity_id, e.entity_type, e.layer, _entity_centroid(e)) for e in drawing.entities]
        text_nodes = [n for n in nodes if n.entity_type.upper() in {"TEXT", "MTEXT"}]
        edges: list[SpatialEdge] = []
        for node in nodes:
            if node in text_nodes or not text_nodes:
                continue
            nearest = min(text_nodes, key=lambda t: distance(node.centroid, t.centroid))
            edges.append(SpatialEdge(node.entity_id, nearest.entity_id, "nearest_text", distance(node.centroid, nearest.centroid)))
        evidence = [make_evidence("analyzer.spatial_graph.summary", "spatial_graph", f"Created {len(nodes)} nodes and {len(edges)} edges", module="hscad.analyzers.spatial_graph_analyzer", source_id=drawing.input_path, confidence=0.78 if nodes else 0.25, data={"node_count": len(nodes), "edge_count": len(edges)})]
        return SpatialGraphAnalysis(nodes, edges, evidence)


def _entity_centroid(entity: DrawingEntity) -> tuple[float, float]:
    pts = entity.points
    if pts:
        return centroid(pts)
    insert = entity.geometry.get("insert")
    if isinstance(insert, (list, tuple)) and len(insert) >= 2:
        return (float(insert[0]), float(insert[1]))
    center = entity.geometry.get("center")
    if isinstance(center, (list, tuple)) and len(center) >= 2:
        return (float(center[0]), float(center[1]))
    return (0.0, 0.0)
