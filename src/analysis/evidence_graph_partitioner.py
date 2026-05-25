from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from src.analysis.entity_loader import read_json, write_json_and_md


def partition_evidence_graph_by_file(workspace: str | Path) -> dict[str, Any]:
    base = Path(workspace)
    evidence = read_json(base / "EVIDENCE_JOIN_FUSION.json")
    nodes = list(evidence.get("nodes") or [])
    edges = list(evidence.get("edges") or [])

    node_by_id = {str(node.get("id")): node for node in nodes if node.get("id")}
    file_to_nodes: dict[str, list[dict[str, Any]]] = defaultdict(list)
    node_to_file: dict[str, str] = {}

    for node in nodes:
        node_id = str(node.get("id") or "")
        file_id = _node_file_id(node)
        node_to_file[node_id] = file_id
        file_to_nodes[file_id].append(node)

    file_to_edges: dict[str, list[dict[str, Any]]] = defaultdict(list)
    cross_file_edges: list[dict[str, Any]] = []

    for edge in edges:
        source_id = str(edge.get("from") or "")
        target_id = str(edge.get("to") or "")
        source_file = node_to_file.get(source_id, "__unassigned__")
        target_file = node_to_file.get(target_id, "__unassigned__")
        if source_file == target_file:
            file_to_edges[source_file].append(edge)
        else:
            cross_file_edges.append({**edge, "source_file": source_file, "target_file": target_file})

    out_dir = base / "evidence_partitions"
    out_dir.mkdir(parents=True, exist_ok=True)

    partitions = []
    for file_id in sorted(set(file_to_nodes) | set(file_to_edges)):
        safe = _safe_filename(file_id)
        payload = {
            "file_id": file_id,
            "node_count": len(file_to_nodes.get(file_id, [])),
            "edge_count": len(file_to_edges.get(file_id, [])),
            "nodes": file_to_nodes.get(file_id, []),
            "edges": file_to_edges.get(file_id, []),
        }
        path = out_dir / f"{safe}.evidence.json"
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        partitions.append({
            "file_id": file_id,
            "path": str(path),
            "node_count": payload["node_count"],
            "edge_count": payload["edge_count"],
        })

    cross_path = out_dir / "__cross_file_edges__.json"
    cross_path.write_text(json.dumps(cross_file_edges, ensure_ascii=False, indent=2, default=str), encoding="utf-8")

    result = {
        "backend": "evidence_graph_partitioner",
        "schema_version": "0.1",
        "summary": {
            "partition_count": len(partitions),
            "node_count": len(nodes),
            "edge_count": len(edges),
            "cross_file_edge_count": len(cross_file_edges),
        },
        "partitions": partitions,
        "cross_file_edges_path": str(cross_path),
        "todo": [
            "Improve file_id propagation in upstream evidence nodes.",
            "Partition by sheet/page inside multi-sheet PDF files.",
            "Add per-file dashboard links.",
            "Add per-file validation score aggregation.",
        ],
        "warnings": ["Nodes without file_id are placed in __unassigned__."],
    }
    return write_json_and_md(base, "EVIDENCE_GRAPH_PARTITIONS", result, _markdown(result))


def _node_file_id(node: dict[str, Any]) -> str:
    for key in ["file_id", "source_file_id", "drawing_file_id"]:
        if node.get(key):
            return str(node[key])
    raw = node.get("raw") or {}
    if isinstance(raw, dict):
        for key in ["file_id", "source_file_id", "drawing_file_id"]:
            if raw.get(key):
                return str(raw[key])
    return "__unassigned__"


def _safe_filename(value: str) -> str:
    safe = "".join(ch if ch.isalnum() or ch in "-_." else "_" for ch in value)
    return safe[:120] or "__empty__"


def _markdown(payload: dict[str, Any]) -> str:
    s = payload.get("summary") or {}
    lines = [
        "# Evidence Graph Partitions",
        "",
        f"- Partitions: `{s.get('partition_count')}`",
        f"- Nodes: `{s.get('node_count')}`",
        f"- Edges: `{s.get('edge_count')}`",
        f"- Cross-file edges: `{s.get('cross_file_edge_count')}`",
        "",
        "| File ID | Nodes | Edges |",
        "|---|---:|---:|",
    ]
    for row in (payload.get("partitions") or [])[:200]:
        lines.append(f"| {row.get('file_id')} | {row.get('node_count')} | {row.get('edge_count')} |")
    lines.append("")
    return "\n".join(lines)
