from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from src.analysis.entity_loader import read_json, write_json_and_md


def export_evidence_graph_tables(workspace: str | Path) -> dict[str, Any]:
    """Export EVIDENCE_JOIN_FUSION.json into lightweight table artifacts.

    This module intentionally avoids heavy dependencies. It writes JSONL + CSV tables.
    DuckDB/Parquet export can consume these later.
    """
    base = Path(workspace)
    evidence = read_json(base / "EVIDENCE_JOIN_FUSION.json")
    nodes = list(evidence.get("nodes") or [])
    edges = list(evidence.get("edges") or [])

    export_dir = base / "evidence_graph"
    export_dir.mkdir(parents=True, exist_ok=True)

    nodes_jsonl = export_dir / "nodes.jsonl"
    edges_jsonl = export_dir / "edges.jsonl"
    nodes_csv = export_dir / "nodes.csv"
    edges_csv = export_dir / "edges.csv"

    _write_jsonl(nodes_jsonl, nodes)
    _write_jsonl(edges_jsonl, edges)

    _write_csv(
        nodes_csv,
        nodes,
        ["id", "kind", "role", "confidence", "source", "text"],
    )
    _write_csv(
        edges_csv,
        edges,
        ["from", "to", "kind", "confidence", "source"],
    )

    payload = {
        "backend": "evidence_graph_exporter",
        "schema_version": "0.1",
        "summary": {
            "node_count": len(nodes),
            "edge_count": len(edges),
            "nodes_jsonl": str(nodes_jsonl),
            "edges_jsonl": str(edges_jsonl),
            "nodes_csv": str(nodes_csv),
            "edges_csv": str(edges_csv),
        },
        "artifacts": [
            str(nodes_jsonl),
            str(edges_jsonl),
            str(nodes_csv),
            str(edges_csv),
        ],
        "todo": [
            "Add DuckDB/Parquet export after validation.",
            "Add per-file partitioned graph export.",
            "Add schema versioned graph tables.",
            "Add Neo4j Cypher export as optional sidecar.",
        ],
        "warnings": [
            "CSV/JSONL export only; no DuckDB/Parquet dependency is required here."
        ],
    }
    return write_json_and_md(base, "EVIDENCE_GRAPH_EXPORT", payload, _markdown(payload))


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")


def _write_csv(path: Path, rows: list[dict[str, Any]], columns: list[str]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key) for key in columns})


def _markdown(payload: dict[str, Any]) -> str:
    s = payload.get("summary") or {}
    return "\n".join([
        "# Evidence Graph Export",
        "",
        f"- Nodes: `{s.get('node_count')}`",
        f"- Edges: `{s.get('edge_count')}`",
        f"- Nodes JSONL: `{s.get('nodes_jsonl')}`",
        f"- Edges JSONL: `{s.get('edges_jsonl')}`",
        f"- Nodes CSV: `{s.get('nodes_csv')}`",
        f"- Edges CSV: `{s.get('edges_csv')}`",
        "",
    ])
