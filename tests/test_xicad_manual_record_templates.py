from __future__ import annotations

import json
from pathlib import Path

from src.orchestrator.xicad_manual_recorder import build_manual_record_template, write_manual_record_template


def test_build_manual_record_template_default_fields():
    template = build_manual_record_template("WAL")
    assert template.alias == "WAL"
    assert template.function == "xiDrawWall"
    assert "observed_prompt_sequence" in template.template
    assert template.template["no_save_confirmed"] is False


def test_write_manual_record_template(tmp_path: Path):
    out = tmp_path / "WAL_template.json"
    path = write_manual_record_template("WAL", out)
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    assert payload["alias"] == "WAL"
    assert payload["template"]["xicad_root"] == "C:/XICAD"
