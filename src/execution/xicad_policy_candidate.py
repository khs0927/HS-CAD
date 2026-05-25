from __future__ import annotations

from dataclasses import asdict, dataclass, field
import re
from typing import Any

from src.execution.xicad_alias_policy import (
    XiCADAliasPolicy,
    build_default_xicad_alias_policies,
)


DANGEROUS_ALIAS_KEYWORDS = {
    "ERASE",
    "DELETE",
    "PURGE",
    "EXPLODE",
    "OVERKILL",
    "AUDIT",
    "RECOVER",
    "QSAVE",
    "SAVE",
    "SAVEAS",
    "CLOSE",
    "OPEN",
    "INSERT",
    "APPLOAD",
    "NETLOAD",
    "SCRIPT",
}


@dataclass(frozen=True)
class XiCADAliasCandidate:
    alias: str
    status: str
    suggested_risk: str
    reason: str
    source: str
    raw_command: str = ""
    existing_policy: dict[str, Any] | None = None
    suggested_policy: dict[str, Any] | None = None
    tags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class XiCADPolicyCandidateReport:
    source: str
    alias_count: int
    existing_count: int
    candidate_count: int
    blocked_candidate_count: int
    review_required_count: int
    candidates: list[XiCADAliasCandidate]
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "alias_count": self.alias_count,
            "existing_count": self.existing_count,
            "candidate_count": self.candidate_count,
            "blocked_candidate_count": self.blocked_candidate_count,
            "review_required_count": self.review_required_count,
            "candidates": [item.to_dict() for item in self.candidates],
            "warnings": self.warnings,
        }


def build_policy_candidates_from_aliases(
    aliases: dict[str, str] | list[str],
    *,
    source: str = "xicad",
    existing_policies: dict[str, XiCADAliasPolicy] | None = None,
) -> XiCADPolicyCandidateReport:
    existing_policies = existing_policies or build_default_xicad_alias_policies()

    if isinstance(aliases, dict):
        rows = [(str(alias).upper(), str(command)) for alias, command in aliases.items()]
    else:
        rows = [(str(alias).upper(), "") for alias in aliases]

    candidates: list[XiCADAliasCandidate] = []
    existing_count = 0
    blocked_count = 0
    review_count = 0

    for alias, raw_command in sorted(rows):
        if not alias:
            continue

        existing = existing_policies.get(alias)
        if existing:
            existing_count += 1
            candidates.append(
                XiCADAliasCandidate(
                    alias=alias,
                    status="existing_policy",
                    suggested_risk=existing.risk,
                    reason="Alias already has an explicit HS-CAD policy.",
                    source=source,
                    raw_command=raw_command,
                    existing_policy=existing.to_dict(),
                    tags=["existing"],
                )
            )
            continue

        if _is_dangerous(alias, raw_command):
            blocked_count += 1
            candidates.append(
                XiCADAliasCandidate(
                    alias=alias,
                    status="blocked_candidate",
                    suggested_risk="blocked",
                    reason="Alias or command text matches dangerous keyword policy.",
                    source=source,
                    raw_command=raw_command,
                    suggested_policy=_suggest_policy(alias, "blocked", raw_command),
                    tags=["dangerous", "blocked", "manual-review-required"],
                )
            )
            continue

        review_count += 1
        candidates.append(
            XiCADAliasCandidate(
                alias=alias,
                status="review_required_candidate",
                suggested_risk="review_required",
                reason="Alias is known from XiCAD data but not yet approved by HS-CAD.",
                source=source,
                raw_command=raw_command,
                suggested_policy=_suggest_policy(alias, "review_required", raw_command),
                tags=["candidate", "manual-review-required"],
            )
        )

    return XiCADPolicyCandidateReport(
        source=source,
        alias_count=len(rows),
        existing_count=existing_count,
        candidate_count=len(candidates) - existing_count,
        blocked_candidate_count=blocked_count,
        review_required_count=review_count,
        candidates=candidates,
        warnings=[
            "This report does not approve execution.",
            "All new aliases require human review before policy promotion.",
            "Execution allowed aliases must remain false by default.",
        ],
    )


def _is_dangerous(alias: str, raw_command: str) -> bool:
    alias_token = alias.upper()
    if alias_token in DANGEROUS_ALIAS_KEYWORDS:
        return True
    command_tokens = set(re.findall(r"[A-Z0-9_]+", raw_command.upper()))
    return bool(command_tokens & DANGEROUS_ALIAS_KEYWORDS)


def _suggest_policy(alias: str, risk: str, raw_command: str) -> dict[str, Any]:
    return {
        "alias": alias,
        "risk": risk,
        "title": f"Candidate policy for {alias}",
        "description": f"Candidate generated from XiCAD alias data. Raw command: {raw_command}",
        "allowed_for_dry_run": risk != "blocked",
        "allowed_for_execution": False,
        "requires_human_review": True,
        "destructive": risk == "blocked",
        "tags": ["generated-candidate"],
        "notes": ["Generated candidate. Do not execute until reviewed and promoted."],
    }
