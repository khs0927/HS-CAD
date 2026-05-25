from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal

AliasRisk = Literal["safe_plan_only", "review_required", "blocked", "unknown"]


@dataclass(frozen=True)
class XiCADAliasPolicy:
    alias: str
    risk: AliasRisk
    title: str
    description: str
    allowed_for_dry_run: bool = True
    allowed_for_execution: bool = False
    requires_human_review: bool = True
    destructive: bool = False
    tags: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_default_xicad_alias_policies() -> dict[str, XiCADAliasPolicy]:
    policies = [
        XiCADAliasPolicy(
            alias="WAL",
            risk="safe_plan_only",
            title="Wall drafting workflow",
            description="XiCAD wall workflow candidate. Plan only until wall style and layer mapping are verified.",
            tags=["wall", "geometry", "review-gated"],
            notes=["Use parsed xiDrawWall styles before allowing execution."],
        ),
        XiCADAliasPolicy(
            alias="COL",
            risk="safe_plan_only",
            title="Column workflow",
            description="Column drafting workflow candidate. Plan only until structural/layer evidence is verified.",
            tags=["column", "structure", "review-gated"],
        ),
        XiCADAliasPolicy(
            alias="D1",
            risk="safe_plan_only",
            title="Door workflow",
            description="Door command candidate. Plan only until door width/frame/layer rules are verified.",
            tags=["door", "opening", "review-gated"],
        ),
        XiCADAliasPolicy(
            alias="W1",
            risk="safe_plan_only",
            title="Window workflow",
            description="Window command candidate. Plan only until window type/layer rules are verified.",
            tags=["window", "opening", "review-gated"],
        ),
        XiCADAliasPolicy(
            alias="PK",
            risk="review_required",
            title="Parking or package workflow",
            description="Alias requires manual classification before dry-run mapping.",
            allowed_for_dry_run=True,
            allowed_for_execution=False,
            requires_human_review=True,
            tags=["unknown-domain", "manual-review"],
        ),
        XiCADAliasPolicy(
            alias="ERASE",
            risk="blocked",
            title="Erase command",
            description="Destructive command. Must never be executed through autonomous workflow.",
            allowed_for_dry_run=False,
            allowed_for_execution=False,
            destructive=True,
            tags=["destructive", "blocked"],
        ),
        XiCADAliasPolicy(
            alias="DELETE",
            risk="blocked",
            title="Delete command",
            description="Destructive command. Must never be executed through autonomous workflow.",
            allowed_for_dry_run=False,
            allowed_for_execution=False,
            destructive=True,
            tags=["destructive", "blocked"],
        ),
        XiCADAliasPolicy(
            alias="PURGE",
            risk="blocked",
            title="Purge command",
            description="Potentially destructive cleanup command. Blocked by default.",
            allowed_for_dry_run=False,
            allowed_for_execution=False,
            destructive=True,
            tags=["cleanup", "blocked"],
        ),
    ]
    return {item.alias.upper(): item for item in policies}


def unknown_alias_policy(alias: str) -> XiCADAliasPolicy:
    return XiCADAliasPolicy(
        alias=alias.upper(),
        risk="unknown",
        title="Unknown XiCAD alias",
        description="Alias is not in HS-CAD allowlist. It must be blocked until manually classified.",
        allowed_for_dry_run=False,
        allowed_for_execution=False,
        requires_human_review=True,
        destructive=False,
        tags=["unknown", "blocked"],
        notes=["Add an explicit XiCADAliasPolicy before using this alias."],
    )
