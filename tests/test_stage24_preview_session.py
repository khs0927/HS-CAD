import json
from pathlib import Path

from src.preview_lifecycle.manager import create_session_from_plan_and_insert_result
from src.preview_lifecycle.store import load_preview_session, save_preview_session


def test_create_session_from_plan_and_insert_result(tmp_path: Path):
    plan = tmp_path / "plan.json"
    result = tmp_path / "result.json"
    plan.write_text(json.dumps({"source_dxf": "a.dxf", "insert_layer": "QA-REVIEW", "base_point": [1, 2, 0]}), encoding="utf-8")
    result.write_text(json.dumps({"inserted_handle": "ABCD", "undo_mark_created": True}), encoding="utf-8")

    session = create_session_from_plan_and_insert_result(plan, result)
    assert session.source_dxf == "a.dxf"
    assert session.inserted_handle == "ABCD"
    assert session.status == "inserted"
    assert session.saved is False

    out = tmp_path / "preview_session.json"
    save_preview_session(session, out)
    loaded = load_preview_session(out)
    assert loaded.inserted_handle == "ABCD"
