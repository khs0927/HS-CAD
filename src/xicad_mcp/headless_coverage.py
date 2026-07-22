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
    "FAM": "headless-core-batch7.json",
    "FTT": "headless-core-batch7.json",
    "T2M": "headless-core-batch7.json",
    "TEC": "headless-core-batch7.json",
    "TJ": "headless-core-batch7.json",
    "TSA": "headless-core-batch7.json",
    "TSE": "headless-core-batch7.json",
    "TSO": "headless-core-batch7.json",
    "TSP": "headless-core-batch7.json",
    "TST": "headless-core-batch7.json",
    "TSW": "headless-core-batch7.json",
    "TW": "headless-core-batch7.json",
    "A2M": "headless-core-batch8.json",
    "ABE": "headless-core-batch8.json",
    "CTX": "headless-core-batch8.json",
    "TC": "headless-core-batch8.json",
    "TE": "headless-core-batch8.json",
    "TFF": "headless-core-batch8.json",
    "TO": "headless-core-batch8.json",
    "TOA": "headless-core-batch8.json",
    "TSH": "headless-core-batch8.json",
    "TSM": "headless-core-batch8.json",
    "DAT": "headless-core-batch8.json",
    "LTX": "headless-core-batch8.json",
    "1": "headless-core-batch9.json",
    "2": "headless-core-batch9.json",
    "3": "headless-core-batch9.json",
    "DOL": "headless-core-batch9.json",
    "ELY": "headless-core-batch9.json",
    "EOO": "headless-core-batch9.json",
    "ESF": "headless-core-batch9.json",
    "ESO": "headless-core-batch9.json",
    "EW": "headless-core-batch9.json",
    "LAM": "headless-core-batch9.json",
    "LC": "headless-core-batch9.json",
    "LCC": "headless-core-batch9.json",
    "LCD": "headless-core-batch10.json",
    "LCO": "headless-core-batch10.json",
    "LCS": "headless-core-batch10.json",
    "LF": "headless-core-batch10.json",
    "LFF": "headless-core-batch10.json",
    "LFK": "headless-core-batch10.json",
    "LK": "headless-core-batch10.json",
    "LLC": "headless-core-batch10.json",
    "LOC": "headless-core-batch10.json",
    "LOS": "headless-core-batch10.json",
    "LP": "headless-core-batch10.json",
    "LST": "headless-core-batch10.json",
    "LT": "headless-core-batch11.json",
    "LTG": "headless-core-batch11.json",
    "LU": "headless-core-batch11.json",
    "LUK": "headless-core-batch11.json",
    "CDE": "headless-core-batch11.json",
    "DCV": "headless-core-batch11.json",
    "DDT": "headless-core-batch11.json",
    "DE": "headless-core-batch11.json",
    "DG": "headless-core-batch11.json",
    "DH": "headless-core-batch11.json",
    "DLA": "headless-core-batch11.json",
    "DLL": "headless-core-batch11.json",
    "DPL": "headless-core-batch12.json",
    "DQ": "headless-core-batch12.json",
    "DSC": "headless-core-batch12.json",
    "DSE": "headless-core-batch12.json",
    "DSM": "headless-core-batch12.json",
    "DTM": "headless-core-batch12.json",
    "DTO": "headless-core-batch12.json",
    "DU": "headless-core-batch12.json",
    "ED": "headless-core-batch12.json",
    "IL": "headless-core-batch12.json",
    "LDA": "headless-core-batch12.json",
    "LSE": "headless-core-batch12.json",
    "LX": "headless-core-batch13.json",
    "SD": "headless-core-batch13.json",
    "TL": "headless-core-batch13.json",
    "2DP": "headless-core-batch13.json",
    "3TP": "headless-core-batch13.json",
    "BOO": "headless-core-batch13.json",
    "BS": "headless-core-batch13.json",
    "CBJ": "headless-core-batch13.json",
    "CM": "headless-core-batch13.json",
    "CMW": "headless-core-batch13.json",
    "DRL": "headless-core-batch13.json",
    "JUL": "headless-core-batch13.json",
    "K": "headless-core-batch14.json",
    "LEX": "headless-core-batch14.json",
    "LXP": "headless-core-batch14.json",
    "ME": "headless-core-batch14.json",
    "P2C": "headless-core-batch14.json",
    "PE": "headless-core-batch14.json",
    "PLB": "headless-core-batch14.json",
    "PLBC": "headless-core-batch14.json",
    "PLE": "headless-core-batch14.json",
    "PLR": "headless-core-batch14.json",
    "PR": "headless-core-batch14.json",
    "REC": "headless-core-batch14.json",
    "CT": "headless-core-batch15.json",
    "DTS": "headless-core-batch15.json",
    "FLT": "headless-core-batch15.json",
    "GEE": "headless-core-batch15.json",
    "STL": "headless-core-batch15.json",
    "COM": "headless-core-batch15.json",
    "EXP": "headless-core-batch15.json",
    "OL": "headless-core-batch15.json",
    "ON": "headless-core-batch15.json",
    "QQ": "headless-core-batch15.json",
    "STT": "headless-core-batch15.json",
    "BE": "headless-core-batch15.json",
    "BLI": "headless-core-batch16.json",
    "BPT": "headless-core-batch16.json",
    "CALENDAR": "headless-core-batch16.json",
    "CEP": "headless-core-batch16.json",
    "CLI": "headless-core-batch16.json",
    "COL": "headless-core-batch16.json",
    "CW": "headless-core-batch16.json",
    "D1": "headless-core-batch16.json",
    "D2": "headless-core-batch16.json",
    "D3": "headless-core-batch16.json",
    "DEV": "headless-core-batch16.json",
    "EED": "headless-core-batch16.json",
    "ELV": "headless-core-batch17.json",
    "EPD": "headless-core-batch17.json",
    "HB": "headless-core-batch17.json",
    "HGRID": "headless-core-batch17.json",
    "HP": "headless-core-batch17.json",
    "INS": "headless-core-batch17.json",
    "PK": "headless-core-batch17.json",
    "PZ": "headless-core-batch17.json",
    "QRC": "headless-core-batch17.json",
    "SCB": "headless-core-batch17.json",
    "STB": "headless-core-batch17.json",
    "STC": "headless-core-batch17.json",
    "STP": "headless-core-batch18.json",
    "TAJ": "headless-core-batch18.json",
    "TRUSS": "headless-core-batch18.json",
    "W1": "headless-core-batch18.json",
    "W2": "headless-core-batch18.json",
    "W3": "headless-core-batch18.json",
    "WO": "headless-core-batch18.json",
    "ZIGZAG": "headless-core-batch18.json",
    "C2E": "headless-core-batch18.json",
    "E2C": "headless-core-batch18.json",
    "HC": "headless-core-batch18.json",
    "HEX": "headless-core-batch18.json",
    "HM": "headless-core-batch19a.json",
    "HPM": "headless-core-batch19a.json",
    "RDS": "headless-core-batch19a.json",
    "SOL": "headless-core-batch19a.json",
    "TB": "headless-core-batch19a.json",
    "TBT": "headless-core-batch19a.json",
    "BAT": "headless-core-batch19b.json",
    "BB": "headless-core-batch19b.json",
    "BRO": "headless-core-batch19b.json",
    "CB": "headless-core-batch19b.json",
    "CUT": "headless-core-batch19b.json",
    "DTP": "headless-core-batch19b.json",
    "FE": "headless-core-batch20a.json",
    "FM": "headless-core-batch20a.json",
    "FR": "headless-core-batch20a.json",
    "FT": "headless-core-batch20a.json",
    "FX": "headless-core-batch20a.json",
    "XT": "headless-core-batch20a.json",
    "ARD": "headless-core-batch20b.json",
    "ARP": "headless-core-batch20b.json",
    "ARV": "headless-core-batch20b.json",
    "CNL": "headless-core-batch20b.json",
    "CR": "headless-core-batch20b.json",
    "CTL": "headless-core-batch20b.json",
    "DAC": "headless-core-batch21a.json",
    "DVC": "headless-core-batch21a.json",
    "EXL": "headless-core-batch21a.json",
    "JL": "headless-core-batch21a.json",
    "MC": "headless-core-batch21a.json",
    "MLC": "headless-core-batch21a.json",
    "MM": "headless-core-batch21b.json",
    "OA": "headless-core-batch21b.json",
    "OAA": "headless-core-batch21b.json",
    "OB": "headless-core-batch21b.json",
    "OE": "headless-core-batch21b.json",
    "OI": "headless-core-batch21b.json",
}

PRODUCTION_USABLE = {"%", "-", "*", "/", "=", "00", "ABC", "BPT", "IL", "LST", "ND", "NP", "NS"}
CAD_MUTATION_TOOL_EXPOSED = {
    "1",
    "2",
    "2DP",
    "3",
    "3TP",
    "ABD",
    "A2M",
    "ABE",
    "APD",
    "BAR",
    "BE",
    "BLI",
    "BOO",
    "CBJ",
    "CB",
    "CALENDAR",
    "CEP",
    "CLI",
    "COL",
    "COI",
    "COR",
    "CP",
    "CDE",
    "DCV",
    "CTX",
    "DAT",
    "DTD",
    "DDT",
    "DE",
    "DEV",
    "DOL",
    "DPL",
    "DRL",
    "DQ",
    "DSC",
    "DSM",
    "DTM",
    "DTO",
    "DU",
    "DVD",
    "ED",
    "EED",
    "FAR",
    "FAM",
    "FTT",
    "ELY",
    "ELV",
    "EPD",
    "HGRID",
    "EOO",
    "ESF",
    "ESO",
    "EW",
    "INA",
    "IL",
    "LIS",
    "LFD",
    "LDA",
    "DLA",
    "DLL",
    "LAM",
    "LC",
    "LCC",
    "LCD",
    "LCO",
    "LCS",
    "LF",
    "LFF",
    "LFK",
    "LK",
    "LLC",
    "LOC",
    "LOS",
    "LP",
    "LTX",
    "LXP",
    "LT",
    "LTG",
    "LU",
    "LUK",
    "LMA",
    "LNA",
    "LPP",
    "LPD",
    "LPS",
    "M2",
    "MTB1",
    "MTB2",
    "NUC",
    "NUMC",
    "PY",
    "QD",
    "RC",
    "SCC",
    "SCD",
    "SD",
    "JD",
    "K",
    "SPN",
    "STT",
    "TAP",
    "T2M",
    "TC",
    "TE",
    "TFF",
    "TBM",
    "TCT",
    "TD",
    "TIC",
    "TIE",
    "TII",
    "TIN",
    "TJ",
    "TO",
    "TOA",
    "TM",
    "TS",
    "TSA",
    "TSE",
    "TSO",
    "TST",
    "TSH",
    "TSM",
    "TSW",
    "TRUSS",
    "TW",
    "WAL",
    "ZIGZAG",
    "ARD",
    "ARP",
    "ARV",
    "CNL",
    "CR",
    "CTL",
}
PLATFORM_EXCLUDED = {"SLD"}
SEMANTIC_RENAME_ONLY = {"3TP", "LII", "RR"}

NEXT_CAMPAIGN = (
    "OM",
    "OO",
    "OT",
    "RDC",
    "RM",
    "SB",
    "SM",
    "SS",
    "WR",
    "BMT",
    "DAS",
    "DBC",
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
