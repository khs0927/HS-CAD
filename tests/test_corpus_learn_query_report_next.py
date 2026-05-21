import json
from pathlib import Path

from src.corpus.corpus_learner import learn_from_kb
from src.corpus.corpus_query import query_kb
from src.corpus.fileized_ingest import ingest_fileized_folder
from src.corpus.report_builder import build_report


def _make_db(tmp_path: Path) -> Path:
    fileized = tmp_path / "fileized" / "json"
    fileized.mkdir(parents=True)
    rec = {
        "file_id": "sample002",
        "source_path": "sample2.dxf",
        "extension": ".dxf",
        "fileizer": "ezdxf",
        "status": "success",
        "texts": [
            {"text": "판넬 150T H빔 접합 상세 후레싱 실란트 피스 고정"},
            {"text": "천장고 2564 경량철골 석고텍스 마감"},
        ],
        "entities": [{"layer": "EXT-PANEL"}, {"layer": "STEEL"}],
    }
    (fileized / "sample002.json").write_text(json.dumps(rec, ensure_ascii=False), encoding="utf-8")
    db_path = tmp_path / "corpus" / "cad_knowledge.sqlite"
    ingest_fileized_folder(tmp_path / "fileized", db_path)
    return db_path


def test_learn_query_report(tmp_path):
    db_path = _make_db(tmp_path)
    summary = learn_from_kb(db_path, out_dir=tmp_path / "out")
    assert summary["counts"]["materials"] > 0
    assert (tmp_path / "out" / "learning_summary.json").exists()

    profile = {
        "layer_rules": [
            {"canonical_element": "PANEL_SYSTEM", "preferred_layer": "WAL1", "confidence": 0.8},
            {"canonical_element": "STRUCTURAL_STEEL", "preferred_layer": "COL", "confidence": 0.8},
        ],
        "dimension_rules": {"preferred_dimension_layer": "치수", "preferred_dimension_style": "300DIM", "confidence": 0.8},
        "titleblock_rules": {"preferred_titleblock_name": "ZIUM_sheet_architect", "confidence": 0.8},
    }
    profile_path = tmp_path / "profile.json"
    profile_path.write_text(json.dumps(profile, ensure_ascii=False), encoding="utf-8")

    result = query_kb(db_path, "판넬 H빔", company_profile_path=profile_path)
    assert result["related_materials"] or result["related_situations"] or result["evidence_texts"]
    assert result["company_output_recommendations"]

    report_path = tmp_path / "report.md"
    build_report(db_path, report_path, company_profile_path=profile_path)
    assert report_path.exists()
    assert "Architectural Drawing Knowledge Corpus Report" in report_path.read_text(encoding="utf-8")
