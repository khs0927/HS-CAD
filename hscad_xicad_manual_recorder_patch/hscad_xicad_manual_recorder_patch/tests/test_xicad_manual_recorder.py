from __future__ import annotations

from pathlib import Path
import json

from src.orchestrator.xicad_manual_recorder import (
    build_record_command_example,
    evidence_from_manual_answers,
    write_manual_evidence_and_validation,
)


def test_evidence_from_manual_answers_sequences():
    evidence = evidence_from_manual_answers(
        "WAL",
        {
            "status": "passed",
            "observed_prompt_sequence": "start|end|thickness",
            "accepted_argument_pattern": "point|point|number",
            "no_save_confirmed": True,
            "no_delete_confirmed": True,
            "no_explode_confirmed": True,
        },
    )
    assert evidence.alias == "WAL"
    assert evidence.observed_prompt_sequence == ("start", "end", "thickness")
    assert evidence.accepted_argument_pattern == ("point", "point", "number")


def test_write_manual_evidence_and_validation(tmp_path: Path):
    paths = write_manual_evidence_and_validation(
        "WAL",
        {
            "status": "failed",
            "notes": "manual test pending",
        },
        tmp_path,
    )
    assert Path(paths["record"]).exists()
    assert Path(paths["validation"]).exists()
    validation = json.loads(Path(paths["validation"]).read_text(encoding="utf-8"))
    assert validation["status"] == "BLOCKED"


def test_build_record_command_example():
    command = build_record_command_example("INS")
    assert "xicad-contract-record" in command
    assert "--alias INS" in command
    assert "--no-save-confirmed" in command
