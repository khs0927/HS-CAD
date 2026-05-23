from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Any

from src.execution.xicad_alias_policy import (
    XiCADAliasPolicy,
    build_default_xicad_alias_policies,
    unknown_alias_policy,
)


@dataclass(frozen=True)
class XiCADAliasClassification:
    raw: str
    alias: str
    policy: XiCADAliasPolicy
    allowed_for_dry_run: bool
    allowed_for_execution: bool
    blocked_reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["policy"] = self.policy.to_dict()
        return data


def extract_alias(raw: str) -> str:
    text = str(raw or "").strip()
    if not text:
        return ""

    match = re.search(r"--alias\s+([A-Za-z0-9_-]+)", text)
    if match:
        return match.group(1).upper()

    tokens = re.findall(r"[A-Za-z0-9_-]+", text)
    if not tokens:
        return ""

    # If the command starts with xicad-safe-plan and no --alias exists, treat as unknown.
    if tokens[0].lower() == "xicad-safe-plan":
        return ""

    return tokens[0].upper()


def classify_xicad_alias(
    raw: str,
    *,
    policies: dict[str, XiCADAliasPolicy] | None = None,
) -> XiCADAliasClassification:
    policies = policies or build_default_xicad_alias_policies()
    alias = extract_alias(raw)
    if not alias:
        policy = unknown_alias_policy("")
        return XiCADAliasClassification(
            raw=raw,
            alias="",
            policy=policy,
            allowed_for_dry_run=False,
            allowed_for_execution=False,
            blocked_reason="No alias could be extracted.",
        )

    policy = policies.get(alias, unknown_alias_policy(alias))
    blocked_reason = ""

    if policy.risk in {"blocked", "unknown"}:
        blocked_reason = f"Alias {alias} is {policy.risk}."

    return XiCADAliasClassification(
        raw=raw,
        alias=alias,
        policy=policy,
        allowed_for_dry_run=policy.allowed_for_dry_run and policy.risk not in {"blocked", "unknown"},
        allowed_for_execution=policy.allowed_for_execution and policy.risk == "safe_plan_only",
        blocked_reason=blocked_reason,
    )
