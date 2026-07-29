from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from scripts.validate_xicad_registry_truth import snapshot_tools, validate_truth
from xicad_mcp.server import create_server

ROOT = Path(__file__).resolve().parents[1]


@dataclass
class _Annotations:
    readOnlyHint: bool


@dataclass
class _Tool:
    name: str
    annotations: _Annotations | None


def _coverage() -> dict[str, Any]:
    commands = [
        {
            "alias": "CT",
            "state": "headless_contract_implemented",
            "cad_mutation_tool_exposed": True,
            "production_usable": False,
        },
        {
            "alias": "ND",
            "state": "headless_contract_implemented",
            "cad_mutation_tool_exposed": False,
            "production_usable": True,
        },
    ]
    return {
        "summary": {
            "total_commands": 2,
            "headless_contract_implemented": 2,
            "production_usable": 1,
        },
        "commands": commands,
    }


def _baseline() -> dict[str, Any]:
    return {
        "headless_contracts": 2,
        "cad_mutation_aliases": 1,
        "cad_free_production_usable": 1,
        "mcp_tools": 2,
        "write_or_destructive_tools": 1,
        "required_tools": ["xicad_execute_live_ct"],
    }


def test_validate_truth_accepts_derived_counts_and_unique_tools() -> None:
    registry = snapshot_tools(
        [
            _Tool("xicad_execute_live_ct", _Annotations(readOnlyHint=False)),
            _Tool("xicad_headless_coverage_summary", _Annotations(readOnlyHint=True)),
        ]
    )

    report = validate_truth(_baseline(), _coverage(), registry)

    assert report.valid
    assert report.observed == {
        "total_commands": 2,
        "headless_contracts": 2,
        "cad_mutation_aliases": 1,
        "cad_free_production_usable": 1,
        "mcp_tools": 2,
        "write_or_destructive_tools": 1,
    }


def test_validate_truth_reports_duplicate_missing_and_stale_claims() -> None:
    coverage = _coverage()
    coverage["summary"]["production_usable"] = 0
    registry = snapshot_tools(
        [
            _Tool("duplicate", _Annotations(readOnlyHint=False)),
            _Tool("duplicate", _Annotations(readOnlyHint=True)),
        ]
    )

    report = validate_truth(_baseline(), coverage, registry)

    assert not report.valid
    message = "\n".join(report.errors)
    assert "duplicate MCP tool names" in message
    assert "required MCP tools are missing" in message
    assert "coverage summary production_usable is stale" in message
    assert "write_or_destructive_tools mismatch" not in message


def test_validate_truth_reports_registry_count_drift() -> None:
    registry = snapshot_tools(
        [_Tool("xicad_execute_live_ct", _Annotations(readOnlyHint=False))]
    )

    report = validate_truth(_baseline(), _coverage(), registry)

    assert not report.valid
    assert "mcp_tools mismatch: observed 1, baseline 2" in report.errors


def test_repository_registry_matches_checked_in_truth_baseline() -> None:
    baseline = json.loads(
        (ROOT / "catalog/governance/xicad-registry-baseline.json").read_text(encoding="utf-8")
    )
    coverage = json.loads(
        (ROOT / "catalog/headless/headless-coverage-357.json").read_text(encoding="utf-8")
    )
    registry = snapshot_tools(asyncio.run(create_server(ROOT).list_tools()))

    report = validate_truth(baseline, coverage, registry)

    assert report.valid, "\n".join(report.errors)
