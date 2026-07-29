#!/usr/bin/env python3
"""Validate xiCAD coverage and MCP registry claims against executable discovery."""

from __future__ import annotations

import argparse
import asyncio
import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


@dataclass(frozen=True)
class RegistrySnapshot:
    tool_names: tuple[str, ...]
    write_or_destructive_tools: int

    @property
    def duplicate_names(self) -> tuple[str, ...]:
        counts = Counter(self.tool_names)
        return tuple(sorted(name for name, count in counts.items() if count > 1))


@dataclass(frozen=True)
class TruthReport:
    errors: tuple[str, ...]
    observed: dict[str, int]

    @property
    def valid(self) -> bool:
        return not self.errors


def snapshot_tools(tools: Iterable[Any]) -> RegistrySnapshot:
    values = tuple(tools)
    names = tuple(str(tool.name) for tool in values)
    write = sum(
        1
        for tool in values
        if getattr(tool, "annotations", None) is not None
        and not bool(tool.annotations.readOnlyHint)
    )
    return RegistrySnapshot(tool_names=names, write_or_destructive_tools=write)


def coverage_counts(coverage: dict[str, Any]) -> dict[str, int]:
    commands = coverage["commands"]
    return {
        "total_commands": len(commands),
        "headless_contracts": sum(
            command.get("state") == "headless_contract_implemented" for command in commands
        ),
        "cad_mutation_aliases": sum(
            bool(command.get("cad_mutation_tool_exposed")) for command in commands
        ),
        "cad_free_production_usable": sum(
            bool(command.get("production_usable")) for command in commands
        ),
    }


def validate_truth(
    baseline: dict[str, Any],
    coverage: dict[str, Any],
    registry: RegistrySnapshot,
) -> TruthReport:
    observed = coverage_counts(coverage)
    observed["mcp_tools"] = len(registry.tool_names)
    observed["write_or_destructive_tools"] = registry.write_or_destructive_tools
    errors: list[str] = []

    if observed["total_commands"] != int(baseline["headless_contracts"]):
        errors.append(
            "coverage command total differs from baseline headless contract total: "
            f"{observed['total_commands']} != {baseline['headless_contracts']}"
        )

    for key in (
        "headless_contracts",
        "cad_mutation_aliases",
        "cad_free_production_usable",
        "mcp_tools",
        "write_or_destructive_tools",
    ):
        expected = int(baseline[key])
        actual = observed[key]
        if actual != expected:
            errors.append(f"{key} mismatch: observed {actual}, baseline {expected}")

    summary = coverage.get("summary", {})
    summary_expectations = {
        "total_commands": observed["total_commands"],
        "headless_contract_implemented": observed["headless_contracts"],
        "production_usable": observed["cad_free_production_usable"],
    }
    for key, actual in summary_expectations.items():
        if key in summary and int(summary[key]) != actual:
            errors.append(
                f"coverage summary {key} is stale: summary {summary[key]}, derived {actual}"
            )

    duplicates = registry.duplicate_names
    if duplicates:
        errors.append("duplicate MCP tool names: " + ", ".join(duplicates))

    names = set(registry.tool_names)
    missing = sorted(set(baseline.get("required_tools", ())) - names)
    if missing:
        errors.append("required MCP tools are missing: " + ", ".join(missing))

    return TruthReport(errors=tuple(errors), observed=observed)


async def discover_registry(root: Path) -> RegistrySnapshot:
    from xicad_mcp.server import create_server

    tools = await create_server(root).list_tools()
    return snapshot_tools(tools)


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument(
        "--baseline",
        type=Path,
        default=Path("catalog/governance/xicad-registry-baseline.json"),
    )
    parser.add_argument(
        "--coverage",
        type=Path,
        default=Path("catalog/headless/headless-coverage-357.json"),
    )
    args = parser.parse_args()
    root = args.root.resolve()
    baseline_path = args.baseline if args.baseline.is_absolute() else root / args.baseline
    coverage_path = args.coverage if args.coverage.is_absolute() else root / args.coverage

    report = validate_truth(
        load_json(baseline_path),
        load_json(coverage_path),
        asyncio.run(discover_registry(root)),
    )
    print(json.dumps({"valid": report.valid, "observed": report.observed, "errors": report.errors}, indent=2))
    if not report.valid:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
