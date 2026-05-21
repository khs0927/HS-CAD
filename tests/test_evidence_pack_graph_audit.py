from pathlib import Path
import json
import sqlite3

from src.corpus.evidence_pack import build_evidence_pack
from src.corpus.relationship_graph import build_relationship_graph
from src.corpus.quality_audit import audit_corpus


def _make_kb(path: Path) -> None:
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE files (file_id TEXT)")
    conn.execute("CREATE TABLE texts (file_id TEXT, text TEXT)")
    conn.execute("CREATE TABLE materials (file_id TEXT, material_name TEXT, normalized_name TEXT, context_text TEXT)")
    conn.execute("CREATE TABLE specifications (file_id TEXT, raw_value TEXT, normalized_value TEXT, spec_type TEXT)")
    conn.execute("CREATE TABLE situations (file_id TEXT, situation_tag TEXT, evidence_text TEXT)")
    conn.execute("CREATE TABLE canonical_elements (file_id TEXT, canonical_element TEXT)")
    conn.execute("CREATE TABLE detail_patterns (file_id TEXT, pattern_name TEXT, notes TEXT)")
    conn.execute("CREATE TABLE architectural_lessons (file_id TEXT, lesson TEXT)")
    conn.execute("CREATE TABLE processing_errors (file_id TEXT, error_message TEXT)")
    conn.execute("INSERT INTO files VALUES ('f1')")
    conn.execute("INSERT INTO texts VALUES ('f1', 'H빔 외부 돌출 판넬 100T 후레싱 실란트 접합 상세')")
    conn.execute("INSERT INTO materials VALUES ('f1', '판넬', 'panel', 'H빔 접합')")
    conn.execute("INSERT INTO specifications VALUES ('f1', '100T', '100T', 'thickness')")
    conn.execute("INSERT INTO situations VALUES ('f1', 'H빔접합', 'H빔 판넬 접합')")
    conn.execute("INSERT INTO canonical_elements VALUES ('f1', 'STRUCTURAL_STEEL')")
    conn.commit()
    conn.close()


def test_evidence_pack_graph_and_audit(tmp_path: Path):
    kb = tmp_path / "cad_knowledge.sqlite"
    out = tmp_path / "out"
    _make_kb(kb)

    pack = build_evidence_pack(kb, "H빔 판넬 100T", out)
    assert pack.hits
    assert (out / "evidence_pack.json").exists()

    graph = build_relationship_graph(kb, out)
    assert graph.nodes
    assert graph.edges
    assert (out / "relationship_graph.json").exists()

    audit = audit_corpus(kb, out)
    assert audit.tables
    assert (out / "corpus_audit.json").exists()
