#!/usr/bin/env python3
"""Build a truthful work queue for xiCAD commands without live CAD mutation adapters."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

FILE_OR_RESOURCE_ALIASES = {
    "COM",
    "EXP",
    "OL",
    "ON",
    "QQ",
    "STL",
    "BAK",
    "CER",
    "E2C",
    "IB",
    "MDL",
    "PB",
    "PBD",
    "PBM",
    "PPP",
    "Q1",
    "Q11",
    "SVS",
    "VSD",
}
READ_ONLY_WORDS = (
    "조회",
    "정보",
    "목록",
    "갯수",
    "개수",
    "계산",
    "면적",
    "길이",
    "거리",
    "확인",
    "찾기",
)
TOPOLOGY_WORDS = (
    "자르",
    "연결",
    "결합",
    "분리",
    "모서리",
    "중심선",
    "폴리선",
    "해치",
    "블럭",
    "곡선",
    "외부참조",
    "그룹",
)
FILE_WORDS = (
    "파일",
    "도면 열",
    "도면 닫",
    "저장",
    "출력",
    "폴더",
    "탐색기",
    "엑셀",
    "가져",
    "내보",
    "훔쳐",
)


def classify(command: dict[str, Any]) -> tuple[str, str]:
    alias = str(command["alias"]).upper()
    description = str(command.get("description", ""))
    category = str(command.get("category", "")).casefold()
    source = str(command.get("contract_source", ""))

    if command.get("production_usable"):
        return "cad_free_production", "already usable without a CAD mutation adapter"

    if alias in FILE_OR_RESOURCE_ALIASES or category in {"open", "plot", "file"} or any(
        word in description for word in FILE_WORDS
    ):
        return (
            "file_or_resource_transaction",
            "requires canonical paths, overwrite policy, file/drawing state checks, and rollback evidence",
        )

    if any(word in description for word in READ_ONLY_WORDS):
        return (
            "read_only_candidate",
            "review whether the contract can be promoted as a CAD-read or pure calculation tool instead of a mutation",
        )

    if source.endswith("batch32.json"):
        return (
            "caller_supplied_exact_change",
            "current contract still needs executable geometry/property payloads and CAD postconditions",
        )

    if any(word in description for word in TOPOLOGY_WORDS):
        return (
            "geometry_or_topology_recovery",
            "needs recovered output geometry/topology and bounded atomic postconditions",
        )

    return (
        "planner_or_help_gap",
        "compare official help and local xiCAD evidence, then either enrich the planner or keep preview-only",
    )


def build_backlog(
    coverage: dict[str, Any],
    help_index: dict[str, str] | None = None,
) -> dict[str, Any]:
    commands = coverage["commands"]
    gaps = [command for command in commands if not command.get("cad_mutation_tool_exposed", False)]
    expected = int(coverage["summary"]["total_commands"]) - sum(
        bool(command.get("cad_mutation_tool_exposed", False)) for command in commands
    )
    if len(gaps) != expected:
        raise ValueError(f"coverage mismatch: expected {expected} non-live commands, found {len(gaps)}")

    help_urls = {key.upper(): value for key, value in (help_index or {}).items()}
    items = []
    counts: Counter[str] = Counter()
    for command in gaps:
        group, next_artifact = classify(command)
        counts[group] += 1
        alias = str(command["alias"]).upper()
        items.append(
            {
                "alias": alias,
                "symbol": command.get("symbol"),
                "description": command.get("description"),
                "category": command.get("category"),
                "contract_source": command.get("contract_source"),
                "workstream": group,
                "official_help_url": help_urls.get(alias),
                "current_next_requirement": command.get("next_requirement"),
                "next_artifact": next_artifact,
                "manual_review_required": True,
            }
        )

    return {
        "schema_version": "1.0",
        "source_release_scope": coverage.get("release_scope"),
        "source_summary": coverage.get("summary"),
        "summary": {
            "non_live_total": len(items),
            "workstream_counts": dict(sorted(counts.items())),
            "manual_review_required": len(items),
        },
        "commands": items,
    }


def load_help_index(path: Path | None) -> dict[str, str]:
    if path is None or not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, dict) and "commands" in payload:
        return {
            str(item["alias"]).upper(): str(item["url"])
            for item in payload["commands"]
            if item.get("url")
        }
    if isinstance(payload, dict):
        return {str(key).upper(): str(value) for key, value in payload.items() if value}
    raise ValueError("help index must be an object or contain a commands array")


def _resolve(root: Path, value: Path) -> Path:
    return value if value.is_absolute() else root / value


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument(
        "--coverage",
        type=Path,
        default=Path("catalog/headless/headless-coverage-357.json"),
    )
    parser.add_argument(
        "--help-index",
        type=Path,
        default=Path("catalog/headless/official-help-index.json"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("catalog/headless/live-gap-backlog.json"),
    )
    args = parser.parse_args()
    root = args.root.resolve()
    coverage_path = _resolve(root, args.coverage)
    help_index_path = _resolve(root, args.help_index)
    output_path = _resolve(root, args.output)

    coverage = json.loads(coverage_path.read_text(encoding="utf-8"))
    backlog = build_backlog(coverage, load_help_index(help_index_path))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(backlog, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        f"wrote {backlog['summary']['non_live_total']} non-live commands "
        f"to {output_path}"
    )


if __name__ == "__main__":
    main()
