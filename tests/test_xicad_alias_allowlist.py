from __future__ import annotations

from pathlib import Path

from src.execution.xicad_alias_classifier import classify_xicad_alias, extract_alias
from src.execution.xicad_alias_plan import build_xicad_alias_allowlist_plan
from src.reports.json_exporter import export_json
from src.workers.xicad_alias_allowlist_worker import run_xicad_alias_allowlist_worker


COMMAND_PLAN = {
    "task": "alias allowlist test",
    "status": "ready_for_human_review",
    "dry_run_steps": [
        {
            "order": 1,
            "step_id": "dry-run-1",
            "title": "Wall plan",
            "risk": "mutation_gated",
            "command_type": "xicad-safe-plan",
            "command_hint": "xicad-safe-plan --alias WAL",
            "source_decision_id": "action:xicad:WAL",
        },
        {
            "order": 2,
            "step_id": "dry-run-2",
            "title": "Dangerous erase",
            "risk": "mutation_gated",
            "command_type": "xicad-safe-plan",
            "command_hint": "xicad-safe-plan --alias ERASE",
            "source_decision_id": "action:xicad:ERASE",
        },
        {
            "order": 3,
            "step_id": "dry-run-3",
            "title": "Unknown alias",
            "risk": "mutation_gated",
            "command_type": "xicad-safe-plan",
            "command_hint": "xicad-safe-plan --alias ABC_UNKNOWN",
            "source_decision_id": "action:xicad:ABC_UNKNOWN",
        },
    ],
    "review_table": [],
    "execution_queue_candidate": {},
    "blocked_reasons": [],
    "warnings": [],
}


def test_extract_alias_from_command_hint():
    assert extract_alias("xicad-safe-plan --alias WAL") == "WAL"
    assert extract_alias("WAL") == "WAL"
    assert extract_alias("xicad-safe-plan") == ""


def test_classify_safe_blocked_and_unknown_aliases():
    wal = classify_xicad_alias("xicad-safe-plan --alias WAL")
    erase = classify_xicad_alias("xicad-safe-plan --alias ERASE")
    unknown = classify_xicad_alias("xicad-safe-plan --alias ABC_UNKNOWN")

    assert wal.allowed_for_dry_run is True
    assert wal.allowed_for_execution is False

    assert erase.allowed_for_dry_run is False
    assert erase.blocked_reason

    assert unknown.allowed_for_dry_run is False
    assert unknown.blocked_reason


def test_build_alias_allowlist_plan_blocks_unsafe_aliases():
    plan = build_xicad_alias_allowlist_plan(COMMAND_PLAN, source_command_plan="synthetic")

    assert plan.status == "blocked"
    assert "WAL" in plan.dry_run_allowed_aliases
    assert "ERASE" in plan.blocked_aliases
    assert "ABC_UNKNOWN" in plan.blocked_aliases
    assert plan.execution_allowed_aliases == []


def test_xicad_alias_allowlist_worker_writes_artifacts(tmp_path: Path):
    command_plan = tmp_path / "DOMAIN_RULE_COMMAND_PLAN.json"
    out_dir = tmp_path / "alias"
    export_json(COMMAND_PLAN, command_plan)

    result = run_xicad_alias_allowlist_worker(command_plan, out_dir=out_dir)

    assert result["status"] == "blocked"
    assert result["blocked_count"] == 2
    assert result["dry_run_allowed_count"] == 1
    assert result["execution_allowed_count"] == 0
    assert Path(result["plan_json"]).exists()
    assert Path(result["report"]).exists()
