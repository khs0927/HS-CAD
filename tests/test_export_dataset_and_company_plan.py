from pathlib import Path
import json
import sqlite3

from src.corpus.export_dataset import export_corpus_jsonl
from src.company_profile.company_output_planner import build_company_output_plan


def test_export_jsonl_and_company_plan(tmp_path: Path):
    kb = tmp_path / "cad_knowledge.sqlite"
    conn = sqlite3.connect(kb)
    conn.execute("CREATE TABLE files (file_id TEXT, source_path TEXT)")
    conn.execute("CREATE TABLE texts (file_id TEXT, text TEXT)")
    conn.execute("CREATE TABLE materials (file_id TEXT, material_name TEXT)")
    conn.execute("INSERT INTO files VALUES ('f1', 'secret/path/sample.dxf')")
    conn.execute("INSERT INTO texts VALUES ('f1', '방음시창 유리 프레임 실란트')")
    conn.execute("INSERT INTO materials VALUES ('f1', '실란트')")
    conn.commit()
    conn.close()

    out_jsonl = tmp_path / "dataset.jsonl"
    count = export_corpus_jsonl(kb, out_jsonl)
    assert count == 1
    line = json.loads(out_jsonl.read_text(encoding="utf-8").splitlines()[0])
    assert line["file"]["source_path"] is None

    evidence = tmp_path / "evidence_pack.json"
    evidence.write_text(json.dumps({"query": "방음시창", "grouped": {"texts": [{"text": "방음시창 유리 프레임 실란트"}]}}), encoding="utf-8")
    profile = tmp_path / "company_drafting_profile.json"
    profile.write_text(
        json.dumps(
            {
                "titleblock_rules": {"preferred_titleblock_name": "ZIUM_sheet_architect"},
                "dimension_rules": {"preferred_dimension_style": "300DIM"},
                "text_style_rules": {"preferred_text_style": "지움EB"},
                "layer_rules": [{"canonical_element": "DIMENSION", "preferred_layer": "치수"}],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    plan = build_company_output_plan(evidence, profile, tmp_path / "plan")
    assert plan.recommended_dimension_style == "300DIM"
    assert (tmp_path / "plan" / "company_output_plan.json").exists()
