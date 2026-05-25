from __future__ import annotations

import json
from pathlib import Path

from scripts.repo_inventory import SAFETY_FLAGS, build_repo_inventory, write_repo_inventory


def test_repo_inventory_collects_core_sections(tmp_path: Path):
    repo = tmp_path / "repo"
    (repo / "src").mkdir(parents=True)
    (repo / "tests").mkdir()
    (repo / "docs").mkdir()
    (repo / ".github" / "workflows").mkdir(parents=True)
    (repo / "src" / "main.py").write_text("import src.app.example_cli\n", encoding="utf-8")
    (repo / "tests" / "test_example.py").write_text("def test_ok():\n    assert True\n", encoding="utf-8")
    (repo / "docs" / "readme.md").write_text("# ok\n", encoding="utf-8")
    (repo / ".github" / "workflows" / "ci.yml").write_text("name: ci\n", encoding="utf-8")
    (repo / "pyproject.toml").write_text("[project]\nname='x'\n", encoding="utf-8")

    payload = build_repo_inventory(repo)

    assert payload["pyproject"]["exists"] is True
    assert payload["src_main"]["registered_app_imports"] == ["src.app.example_cli"]
    assert payload["summary"]["test_count"] == 1
    assert payload["safety_flags"] == SAFETY_FLAGS


def test_write_repo_inventory_writes_json(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    out = tmp_path / "REPO_INVENTORY.json"

    path = write_repo_inventory(repo, out)

    assert path == out
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["outputs_policy"]["outputs_committed"] is False
