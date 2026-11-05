from __future__ import annotations

import argparse
from enum import StrEnum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator


class BinaryRecoveryDecision(StrEnum):
    CLEANUP_HELPER_REVIEW_REQUIRED = "cleanup_helper_review_required"
    DETERMINISTIC_CORE_CANDIDATE = "deterministic_core_candidate"
    SHARED_CORE_CANDIDATE = "shared_core_candidate"
    PLATFORM_UNSUPPORTED = "platform_unsupported"


class BinaryRecoveryCommand(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    alias: str
    legacy_symbol: str
    description: str
    decision: BinaryRecoveryDecision
    target_lane: str
    compiled_entrypoint: str
    compiled_status: str
    compiled_callable: bool = False
    backup_declaration_present: bool
    current_declaration_present: bool
    upgrade_registration_string_present: bool
    helper_evidence: tuple[str, ...] = ()
    core_key: str | None = None
    entity_filter: str | None = None
    unsupported_platforms: tuple[str, ...] = ()
    production_usable: bool = False
    rationale: tuple[str, ...] = ()
    blockers: tuple[str, ...] = ()

    @model_validator(mode="after")
    def validate_state(self) -> BinaryRecoveryCommand:
        if self.compiled_callable:
            raise ValueError("binary recovery rows must not claim a callable entrypoint")
        if self.production_usable:
            raise ValueError("binary recovery cannot mark production usability")
        if self.decision is BinaryRecoveryDecision.SHARED_CORE_CANDIDATE and not self.core_key:
            raise ValueError("shared core candidates require core_key")
        if self.decision is BinaryRecoveryDecision.DETERMINISTIC_CORE_CANDIDATE and not self.entity_filter:
            raise ValueError("deterministic candidates require entity_filter")
        if self.decision is BinaryRecoveryDecision.PLATFORM_UNSUPPORTED:
            if not self.unsupported_platforms:
                raise ValueError("platform unsupported rows require unsupported_platforms")
            if self.target_lane != "platform_exclusion":
                raise ValueError("platform unsupported rows must use platform_exclusion")
        return self


class BinaryRecoverySummary(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    total_aliases: int = Field(ge=0)
    unique_legacy_symbols: int = Field(ge=0)
    compiled_callable: int = Field(ge=0)
    upgrade_registration_strings: int = Field(ge=0)
    deterministic_core_candidates: int = Field(ge=0)
    shared_core_candidates: int = Field(ge=0)
    cleanup_helper_review_required: int = Field(ge=0)
    platform_unsupported: int = Field(ge=0)
    production_usable: int = Field(ge=0)


class BinaryRecoveryReport(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: str = "1.0"
    source: dict[str, str]
    summary: BinaryRecoverySummary
    commands: tuple[BinaryRecoveryCommand, ...]
    next_queue: dict[str, Any]

    @model_validator(mode="after")
    def validate_report(self) -> BinaryRecoveryReport:
        if len(self.commands) != self.summary.total_aliases:
            raise ValueError("summary total does not match command rows")
        aliases = [row.alias.casefold() for row in self.commands]
        if len(aliases) != len(set(aliases)):
            raise ValueError("duplicate binary recovery alias")
        return self

    def find(self, alias_or_symbol: str) -> BinaryRecoveryCommand:
        key = alias_or_symbol.casefold()
        for row in self.commands:
            if row.alias.casefold() == key:
                return row
        matches = [row for row in self.commands if row.legacy_symbol.casefold() == key]
        if len(matches) == 1:
            return matches[0]
        if len(matches) > 1:
            raise KeyError(f"ambiguous symbol {alias_or_symbol}; use an alias")
        raise KeyError(alias_or_symbol)


class FileBinaryRecoveryService:
    def __init__(self, report_path: str | Path):
        self.report_path = Path(report_path)

    def report(self) -> BinaryRecoveryReport:
        return BinaryRecoveryReport.model_validate_json(self.report_path.read_text(encoding="utf-8"))

    def summary(self) -> BinaryRecoverySummary:
        return self.report().summary

    def command(self, key: str) -> BinaryRecoveryCommand:
        return self.report().find(key)

    def queue(self) -> dict[str, Any]:
        return self.report().next_queue


def register_binary_recovery_tools(mcp: Any, service: FileBinaryRecoveryService) -> None:
    from mcp.types import ToolAnnotations

    read_only = ToolAnnotations(
        title="xiCAD Binary Recovery",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    )

    @mcp.tool(
        name="xicad_binary_recovery_summary",
        description="Return the static recovery disposition for seven legacy xiCAD commands whose compiled command entrypoints were not resolved. No CAD execution is performed.",
        annotations=read_only,
    )
    def binary_recovery_summary() -> BinaryRecoverySummary:
        return service.summary()

    @mcp.tool(
        name="xicad_binary_recovery",
        description="Return shortcut, compiled-container, helper and platform evidence for one unresolved legacy xiCAD command.",
        annotations=read_only,
    )
    def binary_recovery(alias_or_symbol: str) -> BinaryRecoveryCommand:
        try:
            return service.command(alias_or_symbol)
        except KeyError as exc:
            raise ValueError(f"No binary recovery record exists for: {alias_or_symbol}") from exc

    @mcp.tool(
        name="xicad_post_binary_implementation_queue",
        description="Return the implementation queue after static binary recovery analysis. This is planning data only and does not claim production availability.",
        annotations=read_only,
    )
    def post_binary_implementation_queue() -> dict[str, Any]:
        return service.queue()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("report")
    parser.add_argument("--command")
    parser.add_argument("--queue", action="store_true")
    args = parser.parse_args()
    service = FileBinaryRecoveryService(args.report)
    if args.command:
        payload: Any = service.command(args.command)
    elif args.queue:
        payload = service.queue()
    else:
        payload = service.report()
    if isinstance(payload, BaseModel):
        print(payload.model_dump_json(indent=2))
    else:
        import json

        print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
