import json
from pathlib import Path

from src.corpus.fileized_ingest import ingest_fileized_folder
from src.corpus.knowledge_store import KnowledgeStore


def test_fileized_ingest_extracts_materials_specs_situations(tmp_path):
    fileized = tmp_path / "fileized" / "json"
    fileized.mkdir(parents=True)
    rec = {
        "file_id": "sample001",
        "source_path": "sample.dxf",
        "relative_path": "sample.dxf",
        "extension": ".dxf",
        "fileizer": "ezdxf",
        "fileizer_version": "test",
        "status": "success",
        "metadata": {"drawing_title": "방음시창 상세도"},
        "layers": [{"name": "A-WALL"}],
        "blocks": [{"name": "WINDOW_BLOCK"}],
        "texts": [
            {"text": "방음시창 3000x1000 복층유리 AL 프레임 실란트 차음성능 STC 45"},
            {"text": "글라스울 판넬 125T H-BEAM 접합 후레싱 코킹"},
        ],
        "entities": [],
    }
    (fileized / "sample001.json").write_text(json.dumps(rec, ensure_ascii=False), encoding="utf-8")

    db_path = tmp_path / "corpus" / "cad_knowledge.sqlite"
    stats = ingest_fileized_folder(tmp_path / "fileized", db_path)

    assert stats["success"] == 1
    store = KnowledgeStore(db_path)
    counts = store.table_counts()
    assert counts["materials"] >= 4
    assert counts["specifications"] >= 2
    assert counts["situations"] >= 1
    search = store.search("방음시창")
    assert search["situations"] or search["texts"]
    store.close()
