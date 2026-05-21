"""Build a lightweight relationship graph from corpus SQLite tables."""

from __future__ import annotations

import json
import sqlite3
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class GraphNode:
    id: str
    label: str
    type: str
    count: int = 1


@dataclass
class GraphEdge:
    source: str
    target: str
    relation: str
    weight: int = 1


@dataclass
class RelationshipGraph:
    nodes: list[GraphNode] = field(default_factory=list)
    edges: list[GraphEdge] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def _connect(kb_path: str | Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(kb_path))
    conn.row_factory = sqlite3.Row
    return conn


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    return conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone() is not None


def _columns(conn: sqlite3.Connection, table: str) -> list[str]:
    if not _table_exists(conn, table):
        return []
    return [r["name"] for r in conn.execute(f"PRAGMA table_info({table})")]


def _pick(row: sqlite3.Row, cols: list[str], candidates: list[str]) -> str | None:
    for c in candidates:
        if c in cols and row[c] not in (None, ""):
            return str(row[c])
    return None


def _items_by_file(conn: sqlite3.Connection, table: str, value_cols: list[str]) -> dict[str, list[str]]:
    result: dict[str, list[str]] = defaultdict(list)
    if not _table_exists(conn, table):
        return result
    cols = _columns(conn, table)
    if "file_id" not in cols:
        return result
    for row in conn.execute(f"SELECT * FROM {table} LIMIT 20000"):
        file_id = str(row["file_id"])
        value = _pick(row, cols, value_cols)
        if value:
            result[file_id].append(value)
    return result


def build_relationship_graph(kb_path: str | Path, out_dir: str | Path) -> RelationshipGraph:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    graph = RelationshipGraph()

    conn = _connect(kb_path)
    try:
        materials = _items_by_file(conn, "materials", ["normalized_name", "material_name", "name", "raw_text"])
        specs = _items_by_file(conn, "specifications", ["normalized_value", "raw_value", "raw_text", "spec_type"])
        situations = _items_by_file(conn, "situations", ["situation_tag", "tag", "raw_text"])
        elements = _items_by_file(conn, "canonical_elements", ["canonical_element", "entity_type", "element"])

        node_counts: Counter[tuple[str, str]] = Counter()
        edge_counts: Counter[tuple[str, str, str]] = Counter()

        all_files = set(materials) | set(specs) | set(situations) | set(elements)
        for file_id in all_files:
            file_materials = list(dict.fromkeys(materials.get(file_id, [])))[:20]
            file_specs = list(dict.fromkeys(specs.get(file_id, [])))[:20]
            file_situations = list(dict.fromkeys(situations.get(file_id, [])))[:20]
            file_elements = list(dict.fromkeys(elements.get(file_id, [])))[:20]

            for value in file_materials:
                node_counts[("material", value)] += 1
            for value in file_specs:
                node_counts[("specification", value)] += 1
            for value in file_situations:
                node_counts[("situation", value)] += 1
            for value in file_elements:
                node_counts[("element", value)] += 1

            for situation in file_situations:
                for material in file_materials:
                    edge_counts[(f"situation:{situation}", f"material:{material}", "uses_material")] += 1
                for spec in file_specs:
                    edge_counts[(f"situation:{situation}", f"specification:{spec}", "has_specification")] += 1
                for element in file_elements:
                    edge_counts[(f"situation:{situation}", f"element:{element}", "involves_element")] += 1
            for material in file_materials:
                for spec in file_specs:
                    edge_counts[(f"material:{material}", f"specification:{spec}", "has_specification")] += 1

        graph.nodes = [
            GraphNode(id=f"{typ}:{label}", label=label, type=typ, count=count)
            for (typ, label), count in node_counts.most_common(500)
        ]
        graph.edges = [
            GraphEdge(source=src, target=dst, relation=rel, weight=weight)
            for (src, dst, rel), weight in edge_counts.most_common(1000)
        ]

        if not graph.nodes:
            graph.warnings.append("No relationship nodes were generated. Check extracted materials/situations/specifications.")

        data = {
            "nodes": [asdict(n) for n in graph.nodes],
            "edges": [asdict(e) for e in graph.edges],
            "warnings": graph.warnings,
        }
        (out / "relationship_graph.json").write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        (out / "relationship_graph.md").write_text(render_graph_markdown(graph), encoding="utf-8")
        return graph
    finally:
        conn.close()


def render_graph_markdown(graph: RelationshipGraph) -> str:
    lines = ["# CAD Corpus Relationship Graph", ""]
    lines.append("## Top Nodes")
    lines.append("")
    for node in graph.nodes[:50]:
        lines.append(f"- `{node.type}` **{node.label}**: {node.count}")
    lines.append("")
    lines.append("## Top Edges")
    lines.append("")
    for edge in graph.edges[:80]:
        lines.append(f"- `{edge.relation}` {edge.source} → {edge.target}: {edge.weight}")
    if graph.warnings:
        lines.append("")
        lines.append("## Warnings")
        for w in graph.warnings:
            lines.append(f"- {w}")
    return "\n".join(lines).rstrip() + "\n"
