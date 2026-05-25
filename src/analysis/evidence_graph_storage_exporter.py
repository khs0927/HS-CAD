from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.analysis.entity_loader import read_json, write_json_and_md


def export_evidence_graph_storage(workspace: str | Path) -> dict[str, Any]:
    """Optional storage exporter for the evidence graph.

    The exporter is intentionally optional:
    - Always writes JSON table artifacts.
    - Writes DuckDB when duckdb is installed.
    - Writes Parquet when pyarrow is installed.
    - Never fails the whole worker if optional dependencies are missing.
    """
    base = Path(workspace)
    evidence = read_json(base / "EVIDENCE_JOIN_FUSION.json")
    nodes = list(evidence.get("nodes") or [])
    edges = list(evidence.get("edges") or [])

    out_dir = base / "evidence_storage"
    out_dir.mkdir(parents=True, exist_ok=True)

    nodes_json = out_dir / "nodes.table.json"
    edges_json = out_dir / "edges.table.json"
    nodes_json.write_text(json.dumps(nodes, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    edges_json.write_text(json.dumps(edges, ensure_ascii=False, indent=2, default=str), encoding="utf-8")

    warnings: list[str] = []
    artifacts = [str(nodes_json), str(edges_json)]

    duckdb_result = _try_duckdb_export(out_dir, nodes, edges)
    warnings.extend(duckdb_result.get("warnings") or [])
    artifacts.extend(duckdb_result.get("artifacts") or [])

    parquet_result = _try_parquet_export(out_dir, nodes, edges)
    warnings.extend(parquet_result.get("warnings") or [])
    artifacts.extend(parquet_result.get("artifacts") or [])

    payload = {
        "backend": "evidence_graph_storage_exporter",
        "schema_version": "0.1",
        "summary": {
            "node_count": len(nodes),
            "edge_count": len(edges),
            "artifact_count": len(artifacts),
            "duckdb_status": duckdb_result.get("status"),
            "parquet_status": parquet_result.get("status"),
        },
        "artifacts": artifacts,
        "duckdb": duckdb_result,
        "parquet": parquet_result,
        "todo": [
            "Add stable schema migration for nodes/edges.",
            "Add per-file partitioned export.",
            "Add relationship indexes in DuckDB after schema stabilizes.",
            "Add graph analytics SQL templates.",
        ],
        "warnings": warnings,
    }
    return write_json_and_md(base, "EVIDENCE_GRAPH_STORAGE_EXPORT", payload, _markdown(payload))


def _try_duckdb_export(out_dir: Path, nodes: list[dict[str, Any]], edges: list[dict[str, Any]]) -> dict[str, Any]:
    try:
        import duckdb  # type: ignore
    except Exception as exc:
        return {
            "status": "unavailable",
            "warnings": [f"duckdb unavailable: {exc}"],
            "artifacts": [],
        }

    db_path = out_dir / "evidence_graph.duckdb"
    try:
        con = duckdb.connect(str(db_path))
        con.execute("CREATE OR REPLACE TABLE evidence_nodes_raw (payload JSON)")
        con.execute("CREATE OR REPLACE TABLE evidence_edges_raw (payload JSON)")
        if nodes:
            con.executemany(
                "INSERT INTO evidence_nodes_raw VALUES (?)",
                [(json.dumps(row, ensure_ascii=False, default=str),) for row in nodes],
            )
        if edges:
            con.executemany(
                "INSERT INTO evidence_edges_raw VALUES (?)",
                [(json.dumps(row, ensure_ascii=False, default=str),) for row in edges],
            )
        con.execute("""
            CREATE OR REPLACE VIEW evidence_nodes AS
            SELECT
              payload->>'id' AS id,
              payload->>'kind' AS kind,
              payload->>'role' AS role,
              try_cast(payload->>'confidence' AS DOUBLE) AS confidence,
              payload->>'source' AS source,
              payload AS raw
            FROM evidence_nodes_raw
        """)
        con.execute("""
            CREATE OR REPLACE VIEW evidence_edges AS
            SELECT
              payload->>'from' AS source_id,
              payload->>'to' AS target_id,
              payload->>'kind' AS kind,
              try_cast(payload->>'confidence' AS DOUBLE) AS confidence,
              payload->>'source' AS source,
              payload AS raw
            FROM evidence_edges_raw
        """)
        con.close()
        return {"status": "ok", "artifacts": [str(db_path)], "warnings": []}
    except Exception as exc:
        return {"status": "error", "artifacts": [], "warnings": [f"duckdb export failed: {exc}"]}


def _try_parquet_export(out_dir: Path, nodes: list[dict[str, Any]], edges: list[dict[str, Any]]) -> dict[str, Any]:
    try:
        import pyarrow as pa  # type: ignore
        import pyarrow.parquet as pq  # type: ignore
    except Exception as exc:
        return {
            "status": "unavailable",
            "warnings": [f"pyarrow unavailable: {exc}"],
            "artifacts": [],
        }

    nodes_path = out_dir / "nodes.parquet"
    edges_path = out_dir / "edges.parquet"
    try:
        node_rows = [_flatten_node(row) for row in nodes]
        edge_rows = [_flatten_edge(row) for row in edges]
        pq.write_table(pa.Table.from_pylist(node_rows or [{"id": None, "kind": None}]), nodes_path)
        pq.write_table(pa.Table.from_pylist(edge_rows or [{"from": None, "to": None, "kind": None}]), edges_path)
        return {"status": "ok", "artifacts": [str(nodes_path), str(edges_path)], "warnings": []}
    except Exception as exc:
        return {"status": "error", "artifacts": [], "warnings": [f"parquet export failed: {exc}"]}


def _flatten_node(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row.get("id"),
        "kind": row.get("kind"),
        "role": row.get("role"),
        "confidence": _float_or_none(row.get("confidence")),
        "source": row.get("source"),
        "text": row.get("text"),
    }


def _flatten_edge(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "from": row.get("from"),
        "to": row.get("to"),
        "kind": row.get("kind"),
        "confidence": _float_or_none(row.get("confidence")),
        "source": row.get("source"),
    }


def _float_or_none(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except Exception:
        return None


def _markdown(payload: dict[str, Any]) -> str:
    s = payload.get("summary") or {}
    lines = [
        "# Evidence Graph Storage Export",
        "",
        f"- Nodes: `{s.get('node_count')}`",
        f"- Edges: `{s.get('edge_count')}`",
        f"- Artifact count: `{s.get('artifact_count')}`",
        f"- DuckDB status: `{s.get('duckdb_status')}`",
        f"- Parquet status: `{s.get('parquet_status')}`",
        "",
        "## Artifacts",
        "",
    ]
    for path in payload.get("artifacts") or []:
        lines.append(f"- `{path}`")
    lines.append("")
    return "\n".join(lines)
