from __future__ import annotations

import argparse
from enum import StrEnum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator


class WrapperLoadPolicy(StrEnum):
    DEFAULT = "default"
    EXPLICIT_OVERRIDE = "explicit_override"


class WrapperState(StrEnum):
    GENERATED_STATIC_VALIDATED = "generated_static_validated"


class CompatibilityWrapper(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    legacy_alias: str
    legacy_symbol: str
    current_alias: str
    current_symbol: str
    compiled_entrypoint: str
    module: str
    load_policy: WrapperLoadPolicy
    alias_collision: bool = False
    output_file: str
    state: WrapperState = WrapperState.GENERATED_STATIC_VALIDATED
    production_usable: bool = False
    blockers: tuple[str, ...] = ()

    @model_validator(mode="after")
    def validate_mapping(self) -> CompatibilityWrapper:
        if self.legacy_symbol.casefold() != self.current_symbol.casefold():
            raise ValueError("compatibility wrapper must preserve the original function")
        if self.alias_collision != (self.load_policy is WrapperLoadPolicy.EXPLICIT_OVERRIDE):
            raise ValueError("alias collisions must use the explicit override profile")
        if self.production_usable:
            raise ValueError("generated wrappers cannot be production-usable without CAD evidence")
        return self


class CompatibilitySummary(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    total: int = Field(ge=0)
    default_profile: int = Field(ge=0)
    explicit_override_profile: int = Field(ge=0)
    static_validated: int = Field(ge=0)
    production_usable: int = Field(ge=0)
    all_static_validated: bool
    all_production_usable: bool


class CompatibilityRegistry(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: str = "1.0"
    release_scope: str = "xicad-legacy-357"
    generated_from: dict[str, str]
    summary: CompatibilitySummary
    wrappers: tuple[CompatibilityWrapper, ...]

    @model_validator(mode="after")
    def validate_registry(self) -> CompatibilityRegistry:
        aliases = [row.legacy_alias.casefold() for row in self.wrappers]
        if len(aliases) != len(set(aliases)):
            raise ValueError("compatibility registry contains duplicate legacy aliases")
        total = len(self.wrappers)
        default_count = sum(row.load_policy is WrapperLoadPolicy.DEFAULT for row in self.wrappers)
        override_count = total - default_count
        static_count = sum(row.state is WrapperState.GENERATED_STATIC_VALIDATED for row in self.wrappers)
        production_count = sum(row.production_usable for row in self.wrappers)
        expected = (total, default_count, override_count, static_count, production_count)
        actual = (
            self.summary.total,
            self.summary.default_profile,
            self.summary.explicit_override_profile,
            self.summary.static_validated,
            self.summary.production_usable,
        )
        if expected != actual:
            raise ValueError("compatibility summary does not match wrapper rows")
        return self

    def find(self, alias_or_symbol: str) -> CompatibilityWrapper:
        key = alias_or_symbol.casefold()
        for row in self.wrappers:
            if row.legacy_alias.casefold() == key:
                return row
        for row in self.wrappers:
            if row.legacy_symbol.casefold() == key:
                return row
        current_matches = tuple(row for row in self.wrappers if row.current_alias.casefold() == key)
        if len(current_matches) == 1:
            return current_matches[0]
        raise KeyError(alias_or_symbol)

    def plan(
        self,
        include_explicit_overrides: bool = False,
    ) -> tuple[CompatibilityWrapper, ...]:
        return tuple(
            row for row in self.wrappers if row.load_policy is WrapperLoadPolicy.DEFAULT or include_explicit_overrides
        )


class CompatibilityPlan(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    count: int = Field(ge=0)
    includes_explicit_overrides: bool
    wrappers: tuple[CompatibilityWrapper, ...]


class FileCompatibilityService:
    def __init__(self, registry_path: str | Path):
        self.registry_path = Path(registry_path)

    def registry(self) -> CompatibilityRegistry:
        return CompatibilityRegistry.model_validate_json(self.registry_path.read_text(encoding="utf-8"))

    def summary(self) -> CompatibilitySummary:
        return self.registry().summary

    def wrapper(self, alias_or_symbol: str) -> CompatibilityWrapper:
        return self.registry().find(alias_or_symbol)

    def plan(self, include_explicit_overrides: bool = False) -> CompatibilityPlan:
        wrappers = self.registry().plan(include_explicit_overrides)
        return CompatibilityPlan(
            count=len(wrappers),
            includes_explicit_overrides=include_explicit_overrides,
            wrappers=wrappers,
        )


def register_compatibility_alias_tools(
    mcp: Any,
    service: FileCompatibilityService,
) -> None:
    from mcp.types import ToolAnnotations

    read_only = ToolAnnotations(
        title="xiCAD Compatibility Aliases",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    )

    @mcp.tool(
        name="xicad_compatibility_alias_summary",
        description=(
            "Return the static validation summary for generated legacy xiCAD "
            "alias wrappers. This does not claim CAD runtime or production evidence."
        ),
        annotations=read_only,
    )
    def compatibility_alias_summary() -> CompatibilitySummary:
        return service.summary()

    @mcp.tool(
        name="xicad_compatibility_alias",
        description=(
            "Return the reviewed legacy alias mapping, load policy, generated file "
            "and remaining evidence blockers for one compatibility wrapper."
        ),
        annotations=read_only,
    )
    def compatibility_alias(alias_or_symbol: str) -> CompatibilityWrapper:
        try:
            return service.wrapper(alias_or_symbol)
        except KeyError as exc:
            raise ValueError(f"No generated compatibility wrapper exists for: {alias_or_symbol}") from exc

    @mcp.tool(
        name="xicad_compatibility_alias_plan",
        description=(
            "Return the deterministic wrapper load plan. Explicit collision overrides "
            "are excluded unless requested and remain non-production."
        ),
        annotations=read_only,
    )
    def compatibility_alias_plan(
        include_explicit_overrides: bool = False,
    ) -> CompatibilityPlan:
        return service.plan(include_explicit_overrides)


def write_registry(registry: CompatibilityRegistry, path: str | Path) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(registry.model_dump_json(indent=2), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("registry")
    parser.add_argument("--alias")
    parser.add_argument("--include-explicit-overrides", action="store_true")
    args = parser.parse_args()
    service = FileCompatibilityService(args.registry)
    if args.alias:
        payload: BaseModel = service.wrapper(args.alias)
    else:
        payload = service.plan(args.include_explicit_overrides)
    print(payload.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
