from __future__ import annotations

import argparse
from enum import StrEnum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator


class SemanticDecision(StrEnum):
    ALIAS_PRESERVED_RENAME_CANDIDATE = "alias_preserved_rename_candidate"
    SEMANTIC_CONFLICT = "semantic_conflict"


class ReconciliationCommand(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    alias: str
    legacy_symbol: str
    current_symbol: str
    legacy_description: str
    current_description: str
    compiled_entrypoint: str
    compiled_status: str
    module: str | None = None
    decision: SemanticDecision
    static_alias_invocation_candidate: bool
    code_wrapper_required: bool
    production_usable: bool = False
    evidence_paths: tuple[str, ...] = ()
    rationale: tuple[str, ...] = ()
    blockers: tuple[str, ...] = ()

    @model_validator(mode="after")
    def validate_decision(self) -> ReconciliationCommand:
        if self.decision is SemanticDecision.ALIAS_PRESERVED_RENAME_CANDIDATE:
            if not self.static_alias_invocation_candidate:
                raise ValueError("rename candidates must remain statically invocable by alias")
            if self.code_wrapper_required:
                raise ValueError("alias-preserved rename candidates do not need wrappers")
        else:
            if self.static_alias_invocation_candidate:
                raise ValueError("semantic conflicts cannot be legacy invocation candidates")
            if not self.code_wrapper_required:
                raise ValueError("semantic conflicts require replacement implementation")
        if self.production_usable:
            raise ValueError("static reconciliation cannot mark production usability")
        return self


class ReconciliationSummary(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    total: int = Field(ge=0)
    alias_preserved_rename_candidates: int = Field(ge=0)
    semantic_conflicts: int = Field(ge=0)
    legacy_alias_static_candidates_added: int = Field(ge=0)
    remaining_code_commands: int = Field(ge=0)
    production_usable: int = Field(ge=0)


class ReconciliationReport(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: str = "1.0"
    source: dict[str, str]
    summary: ReconciliationSummary
    commands: tuple[ReconciliationCommand, ...]
    next_queue: dict[str, Any]

    @model_validator(mode="after")
    def validate_report(self) -> ReconciliationReport:
        if len(self.commands) != self.summary.total:
            raise ValueError("summary total does not match reconciliation rows")
        aliases = [row.alias.casefold() for row in self.commands]
        if len(aliases) != len(set(aliases)):
            raise ValueError("duplicate semantic reconciliation alias")
        return self

    def find(self, alias_or_symbol: str) -> ReconciliationCommand:
        key = alias_or_symbol.casefold()
        for row in self.commands:
            if row.alias.casefold() == key:
                return row
        for row in self.commands:
            if key in {row.legacy_symbol.casefold(), row.current_symbol.casefold()}:
                return row
        raise KeyError(alias_or_symbol)


class FileReconciliationService:
    def __init__(self, report_path: str | Path):
        self.report_path = Path(report_path)

    def report(self) -> ReconciliationReport:
        return ReconciliationReport.model_validate_json(self.report_path.read_text(encoding="utf-8"))

    def summary(self) -> ReconciliationSummary:
        return self.report().summary

    def command(self, key: str) -> ReconciliationCommand:
        return self.report().find(key)


def register_semantic_reconciliation_tools(mcp: Any, service: FileReconciliationService) -> None:
    from mcp.types import ToolAnnotations

    read_only = ToolAnnotations(
        title="xiCAD Semantic Reconciliation",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    )

    @mcp.tool(
        name="xicad_semantic_reconciliation_summary",
        description="Return static decisions for legacy aliases whose current function names or meanings changed. No CAD runtime equivalence is claimed.",
        annotations=read_only,
    )
    def semantic_reconciliation_summary() -> ReconciliationSummary:
        return service.summary()

    @mcp.tool(
        name="xicad_semantic_reconciliation",
        description="Return old/current descriptions, compiled evidence, decision and blockers for one changed xiCAD alias.",
        annotations=read_only,
    )
    def semantic_reconciliation(alias_or_symbol: str) -> ReconciliationCommand:
        try:
            return service.command(alias_or_symbol)
        except KeyError as exc:
            raise ValueError(f"No semantic reconciliation record exists for: {alias_or_symbol}") from exc


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("report")
    parser.add_argument("--command")
    args = parser.parse_args()
    service = FileReconciliationService(args.report)
    payload = service.command(args.command) if args.command else service.report()
    print(payload.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
