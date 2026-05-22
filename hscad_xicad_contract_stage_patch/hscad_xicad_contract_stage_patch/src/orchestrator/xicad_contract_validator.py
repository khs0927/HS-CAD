from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any
import json

from .xicad_contracts import XiCADContractEvidence, XiCADPromotionCandidate, default_contract_for_alias


@dataclass(frozen=True)
class ContractValidationResult:
    alias: str
    can_promote: bool
    status: str
    missing: list[str]
    warnings: list[str]
    promotion_candidate: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


REQUIRED_TEXT_FIELDS = (
    "manual_zwcad_version",
    "output_observation",
    "rollback_observation",
    "safety_observation",
)

REQUIRED_SEQUENCE_FIELDS = (
    "observed_prompt_sequence",
    "accepted_argument_pattern",
)


def validate_contract_evidence(evidence: XiCADContractEvidence, evidence_path: str | Path = "") -> ContractValidationResult:
    missing: list[str] = []
    warnings: list[str] = []

    if evidence.status.lower() != "passed":
        missing.append("status must be passed")

    if not (evidence.xicad_version or evidence.xicad_root):
        missing.append("xicad_version or xicad_root")

    for field_name in REQUIRED_TEXT_FIELDS:
        if not str(getattr(evidence, field_name, "")).strip():
            missing.append(field_name)

    for field_name in REQUIRED_SEQUENCE_FIELDS:
        if not tuple(getattr(evidence, field_name, ())):
            missing.append(field_name)

    if not evidence.no_save_confirmed:
        missing.append("no_save_confirmed")
    if not evidence.no_delete_confirmed:
        missing.append("no_delete_confirmed")
    if not evidence.no_explode_confirmed:
        missing.append("no_explode_confirmed")

    contract = default_contract_for_alias(evidence.alias)
    if contract.alias == "UNKNOWN":
        warnings.append("Unknown alias; promotion should be manually reviewed with extra care.")

    can_promote = not missing
    candidate = None
    if can_promote:
        candidate_obj = XiCADPromotionCandidate(
            alias=contract.alias,
            function=contract.function,
            verified=True,
            scriptable=True,
            auto_run_allowed=False,
            evidence_path=str(evidence_path),
            review_required=True,
            notes="Candidate only. Do not update recipe_registry without human review.",
        )
        candidate = candidate_obj.to_dict()

    return ContractValidationResult(
        alias=evidence.alias.upper(),
        can_promote=can_promote,
        status="PASS" if can_promote else "BLOCKED",
        missing=missing,
        warnings=warnings,
        promotion_candidate=candidate,
    )


def write_validation_result(result: ContractValidationResult, out_path: str | Path) -> str:
    path = Path(out_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    return str(path)


def write_promotion_candidate(result: ContractValidationResult, out_path: str | Path) -> str:
    if not result.can_promote or not result.promotion_candidate:
        raise ValueError("Contract evidence is not sufficient for a promotion candidate.")
    path = Path(out_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result.promotion_candidate, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(path)
