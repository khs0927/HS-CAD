from __future__ import annotations

from pathlib import Path

from src.execution.xicad_policy_candidate import build_policy_candidates_from_aliases
from src.execution.xicad_policy_loader import load_xicad_alias_policies
from src.reports.json_exporter import export_json


def test_policy_candidate_classifies_existing_blocked_and_review_required():
    report = build_policy_candidates_from_aliases(
        {
            "WAL": "wall command",
            "ERASE": "erase command",
            "ABC": "custom command",
        }
    )

    rows = {item.alias: item for item in report.candidates}

    assert rows["WAL"].status == "existing_policy"
    assert rows["ERASE"].status == "existing_policy" or rows["ERASE"].status == "blocked_candidate"
    assert rows["ABC"].status == "review_required_candidate"
    assert report.review_required_count >= 1


def test_policy_loader_forces_execution_false(tmp_path: Path):
    path = tmp_path / "policy.json"
    export_json(
        {
            "policies": [
                {
                    "alias": "ABC",
                    "risk": "safe_plan_only",
                    "title": "ABC",
                    "description": "test",
                    "allowed_for_dry_run": True,
                    "allowed_for_execution": True,
                }
            ]
        },
        path,
    )

    policies = load_xicad_alias_policies(override_path=path)

    assert policies["ABC"].allowed_for_dry_run is True
    assert policies["ABC"].allowed_for_execution is False
