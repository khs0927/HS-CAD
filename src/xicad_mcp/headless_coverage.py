from __future__ import annotations

import csv
from enum import StrEnum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class HeadlessState(StrEnum):
    IMPLEMENTED = "headless_contract_implemented"
    PLATFORM_EXCLUDED = "platform_excluded"
    WRAPPER_ONLY = "legacy_wrapper_only"
    SEMANTIC_RENAME_ONLY = "semantic_rename_legacy_only"
    LEGACY_BINARY_ONLY = "legacy_binary_only"


class HeadlessCoverageRow(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    alias: str
    symbol: str
    description: str
    category: str
    state: HeadlessState
    contract_source: str | None = None
    dialog_free: bool = False
    cad_mutation_tool_exposed: bool = False
    production_usable: bool = False
    legacy_equivalence_verified_in_cad: bool = False
    next_requirement: str


class HeadlessCoverageSummary(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    total_commands: int = Field(ge=0)
    headless_contract_implemented: int = Field(ge=0)
    production_usable: int = Field(ge=0)
    platform_excluded: int = Field(ge=0)
    wrapper_only: int = Field(ge=0)
    semantic_rename_only: int = Field(ge=0)
    legacy_binary_only: int = Field(ge=0)
    headless_contract_percent: float = Field(ge=0, le=100)
    production_usable_percent: float = Field(ge=0, le=100)


class HeadlessCoverageReport(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    schema_version: str = "1.0"
    release_scope: str = "xicad-legacy-357"
    summary: HeadlessCoverageSummary
    commands: tuple[HeadlessCoverageRow, ...]
    next_campaign: tuple[str, ...]


HEADLESS_CONTRACTS: dict[str, str] = {
    "APD": "maintenance-core-contracts.json",
    "LFD": "maintenance-core-contracts.json",
    "LPD": "maintenance-core-contracts.json",
    "*": "headless-core-batch1.json",
    "CP": "headless-core-batch1.json",
    "RC": "headless-core-batch1.json",
    "LPP": "headless-core-batch1.json",
    "LPS": "headless-core-batch1.json",
    "TCT": "headless-core-batch1.json",
    "DTD": "headless-core-batch2.json",
    "DVD": "headless-core-batch2.json",
    "JD": "headless-core-batch2.json",
    "SCC": "headless-core-batch2.json",
    "SCD": "headless-core-batch2.json",
    "TBM": "headless-core-batch2.json",
    "BAR": "headless-core-batch3.json",
    "ABD": "headless-core-batch3.json",
    "AGD": "headless-core-batch3.json",
    "LPU": "headless-core-batch3.json",
    "MTB1": "headless-core-batch3.json",
    "MTB2": "headless-core-batch3.json",
    "WAL": "first-batch-contracts.json / wall_core.py",
    "%": "headless-core-batch4.json",
    "-": "headless-core-batch4.json",
    "/": "headless-core-batch4.json",
    "=": "headless-core-batch4.json",
    "00": "headless-core-batch4.json",
    "ABC": "headless-core-batch4.json",
    "COI": "headless-core-batch5.json",
    "COR": "headless-core-batch5.json",
    "ND": "headless-core-batch5.json",
    "NP": "headless-core-batch5.json",
    "NS": "headless-core-batch5.json",
    "NUC": "headless-core-batch5.json",
    "PY": "headless-core-batch5.json",
    "FAR": "headless-core-batch5.json",
    "TAP": "headless-core-batch5.json",
    "TD": "headless-core-batch5.json",
    "TM": "headless-core-batch5.json",
    "TS": "headless-core-batch5.json",
    "M2": "headless-core-batch6.json",
    "INA": "headless-core-batch6.json",
    "LIS": "headless-core-batch6.json",
    "LMA": "headless-core-batch6.json",
    "LNA": "headless-core-batch6.json",
    "QD": "headless-core-batch6.json",
    "SPN": "headless-core-batch6.json",
    "NUMC": "headless-core-batch6.json",
    "TIC": "headless-core-batch6.json",
    "TIE": "headless-core-batch6.json",
    "TII": "headless-core-batch6.json",
    "TIN": "headless-core-batch6.json",
}

PRODUCTION_USABLE = {"%", "-", "/", "=", "00", "ABC"}
CAD_MUTATION_TOOL_EXPOSED = {"COI", "COR", "FAR", "NUC", "TAP", "TS", "WAL"}
PLATFORM_EXCLUDED = {"SLD"}
SEMANTIC_RENAME_ONLY = {"3TP", "LII", "RR"}

NEXT_CAMPAIGN = (
    "FAM",
    "FTT",
    "T2M",
    "TEC",
    "TJ",
    "TSA",
    "TSE",
    "TSO",
    "TSP",
    "TST",
    "TSW",
    "TW",
)


def _parse_inventory(path: str | Path) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    category = "Unclassified"
    text = Path(path).read_text(encoding="utf-8", errors="replace")
    for raw in text.splitlines():
        stripped = raw.strip()
        if not stripped:
            continue
        if stripped.startswith("*Sec"):
            category = stripped.removeprefix("*Sec") or "Unclassified"
            continue
        if ";" not in raw:
            continue
        parts = [part.strip() for part in raw.split(";")]
        if len(parts) < 3 or not parts[0]:
            continue
        alias = parts[0]
        if alias in seen:
            continue
        seen.add(alias)
        rows.append(
            {
                "alias": alias,
                "symbol": parts[1],
                "description": parts[2],
                "category": category,
            }
        )
    return rows


def build_headless_coverage(
    inventory_path: str | Path,
    wrapper_aliases: set[str],
) -> HeadlessCoverageReport:
    rows: list[HeadlessCoverageRow] = []
    for item in _parse_inventory(inventory_path):
        alias = item["alias"]
        if alias in HEADLESS_CONTRACTS:
            state = HeadlessState.IMPLEMENTED
            if alias in PRODUCTION_USABLE:
                next_requirement = "none for pure arithmetic"
            elif alias in CAD_MUTATION_TOOL_EXPOSED:
                next_requirement = "legacy equivalence verification and ZWCAD 2025 smoke"
            else:
                next_requirement = "CAD adapter, fixture postconditions, Undo restoration, and ZWCAD 2025/2026 smoke"
            row = HeadlessCoverageRow(
                **item,
                state=state,
                contract_source=HEADLESS_CONTRACTS[alias],
                dialog_free=True,
                cad_mutation_tool_exposed=alias in CAD_MUTATION_TOOL_EXPOSED,
                production_usable=alias in PRODUCTION_USABLE,
                next_requirement=next_requirement,
            )
        elif alias in PLATFORM_EXCLUDED:
            row = HeadlessCoverageRow(
                **item,
                state=HeadlessState.PLATFORM_EXCLUDED,
                next_requirement="retain explicit ZWCAD exclusion or implement a separately reviewed platform adapter",
            )
        elif alias in wrapper_aliases:
            row = HeadlessCoverageRow(
                **item,
                state=HeadlessState.WRAPPER_ONLY,
                next_requirement="capture prompts/DCL decisions and replace the legacy invocation with a structured headless core",
            )
        elif alias in SEMANTIC_RENAME_ONLY:
            row = HeadlessCoverageRow(
                **item,
                state=HeadlessState.SEMANTIC_RENAME_ONLY,
                next_requirement="capture the current command input/output contract and implement a structured headless core",
            )
        else:
            row = HeadlessCoverageRow(
                **item,
                state=HeadlessState.LEGACY_BINARY_ONLY,
                next_requirement="reverse-analyze prompts/DCL/assets and implement a structured headless core",
            )
        rows.append(row)

    counts = {state: 0 for state in HeadlessState}
    production = 0
    for row in rows:
        counts[row.state] += 1
        production += int(row.production_usable)
    total = len(rows)
    summary = HeadlessCoverageSummary(
        total_commands=total,
        headless_contract_implemented=counts[HeadlessState.IMPLEMENTED],
        production_usable=production,
        platform_excluded=counts[HeadlessState.PLATFORM_EXCLUDED],
        wrapper_only=counts[HeadlessState.WRAPPER_ONLY],
        semantic_rename_only=counts[HeadlessState.SEMANTIC_RENAME_ONLY],
        legacy_binary_only=counts[HeadlessState.LEGACY_BINARY_ONLY],
        headless_contract_percent=round(counts[HeadlessState.IMPLEMENTED] / total * 100, 2),
        production_usable_percent=round(production / total * 100, 2),
    )
    return HeadlessCoverageReport(summary=summary, commands=tuple(rows), next_campaign=NEXT_CAMPAIGN)


def write_report(report: HeadlessCoverageReport, json_path: str | Path, csv_path: str | Path) -> None:
    Path(json_path).write_text(report.model_dump_json(indent=2) + "\n", encoding="utf-8")
    with Path(csv_path).open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(
            stream,
            fieldnames=[
                "alias",
                "symbol",
                "description",
                "category",
                "state",
                "contract_source",
                "dialog_free",
                "cad_mutation_tool_exposed",
                "production_usable",
                "legacy_equivalence_verified_in_cad",
                "next_requirement",
            ],
        )
        writer.writeheader()
        for row in report.commands:
            payload = row.model_dump(mode="json")
            writer.writerow(payload)


def register_headless_coverage_tools(mcp: Any, report: HeadlessCoverageReport) -> None:
    from mcp.types import ToolAnnotations

    read_only = ToolAnnotations(
        title="xiCAD Headless Coverage",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    )

    @mcp.tool(
        name="xicad_headless_coverage_summary",
        description="Return the truthful dialog-free coverage summary for the frozen xiCAD 357-command scope.",
        annotations=read_only,
    )
    def mcp_headless_coverage_summary() -> HeadlessCoverageSummary:
        return report.summary

    @mcp.tool(
        name="xicad_headless_command_status",
        description="Return the headless status for one frozen legacy alias.",
        annotations=read_only,
    )
    def mcp_headless_command_status(alias: str) -> HeadlessCoverageRow:
        key = alias.strip().casefold()
        for row in report.commands:
            if row.alias.casefold() == key:
                return row
        raise ValueError(f"unknown frozen legacy alias: {alias}")
