from pathlib import Path
import sqlite3

from src.corpus.query_expander import expand_query
from src.corpus.search_ranker import search_corpus


def test_query_expander_adds_domain_terms():
    expanded = expand_query("판넬 H빔 접합")
    terms = expanded.all_terms
    assert "판넬" in terms
    assert any("h" in t for t in terms)
    assert any("실란트" in t or "후레싱" in t or "샌드위치" in t for t in terms)


def test_search_ranker_finds_materials(tmp_path: Path):
    kb = tmp_path / "cad_knowledge.sqlite"
    conn = sqlite3.connect(kb)
    conn.execute("CREATE TABLE materials (file_id TEXT, material_name TEXT, normalized_name TEXT, context_text TEXT)")
    conn.execute("INSERT INTO materials VALUES ('f1', '글라스울패널', 'glasswool_panel', 'H빔 접합부 판넬 후레싱 실란트')")
    conn.commit()
    conn.close()

    hits = search_corpus(kb, "판넬 H빔 접합", limit=5)
    assert hits
    assert hits[0]["table"] == "materials"
