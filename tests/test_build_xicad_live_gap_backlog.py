from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from scripts.build_xicad_live_gap_backlog import build_backlog, classify, load_help_index


def _command(alias: str, **updates: object) -> dict[str, Any]:
    command: dict[str, Any] = {
        "alias": alias,
        "symbol": f"xi{alias}",
        "description": "일반 변경",
        "category": "Modify",
        "contract_source": "headless-core-batch20a.json",
        "cad_mutation_tool_exposed": False,
        "production_usable": False,
        "next_requirement": "CAD adapter",
    }
    command.update(updates)
    return command


def test_classify_prefers_truthful_non_mutation_and_transaction_groups() -> None:
    assert classify(_command("ND", production_usable=True))[0] == "cad_free_production"
    assert classify(_command("QQ", description="도면 일괄 닫기", category="Open"))[0] == (
        "file_or_resource_transaction"
    )
    assert classify(_command("LII", description="객체 정보 조회"))[0] == "read_only_candidate"
    assert classify(_command("CE", description="중심선 그리기"))[0] == "geometry_or_topology_recovery"
    assert classify(_command("BBB", contract_source="headless-core-batch32.json"))[0] == (
        "caller_supplied_exact_change"
    )


def test_build_backlog_counts_every_non_live_command_once() -> None:
    coverage = {
        "release_scope": "xicad-legacy-357",
        "summary": {"total_commands": 4},
        "commands": [
            _command("ND", production_usable=True),
            _command("QQ", description="도면 일괄 닫기", category="Open"),
            _command("CE", description="중심선 그리기"),
            _command("CT", cad_mutation_tool_exposed=True),
        ],
    }

    backlog = build_backlog(coverage, {"CE": "https://izzarder.com/201"})

    assert backlog["summary"]["non_live_total"] == 3
    assert {item["alias"] for item in backlog["commands"]} == {"ND", "QQ", "CE"}
    ce = next(item for item in backlog["commands"] if item["alias"] == "CE")
    assert ce["official_help_url"] == "https://izzarder.com/201"
    assert all(item["manual_review_required"] for item in backlog["commands"])


def test_load_help_index_reads_enriched_command_records(tmp_path: Path) -> None:
    path = tmp_path / "help.json"
    path.write_text(
        json.dumps(
            {
                "commands": [
                    {
                        "alias": "D1",
                        "url": "https://izzarder.com/171",
                        "status": "planner_incomplete",
                    },
                    {"alias": "NOURL", "status": "unverified"},
                ]
            }
        ),
        encoding="utf-8",
    )

    assert load_help_index(path) == {"D1": "https://izzarder.com/171"}
