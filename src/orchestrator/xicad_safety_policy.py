from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


SAFE_LOOKUP = "SAFE_LOOKUP"
INTERACTIVE_PREVIEW = "INTERACTIVE_PREVIEW"
REVIEW_REQUIRED = "REVIEW_REQUIRED"
HIGH_RISK = "HIGH_RISK"
BLOCKED = "BLOCKED"

RISK_ORDER = {
    SAFE_LOOKUP: 0,
    INTERACTIVE_PREVIEW: 1,
    REVIEW_REQUIRED: 2,
    HIGH_RISK: 3,
    BLOCKED: 4,
}

BLOCKED_ALIASES = {
    "ABX",  # internal all block explode
    "ELY",  # delete objects on selected layer
    "CUT",  # delete inside closed object
    "AGD",  # delete ghost objects
    "APD",  # delete point objects
    "PBD",  # delete plot boxes
    "QQ",   # close drawings
    "OPA",  # reopen without save
}

HIGH_RISK_ALIASES = {
    "LPU",  # purge DGN linetypes
    "PPP",  # plot batch
    "PB",
    "CER",
    "BAK",
}

BLOCKED_KEYWORDS = (
    "삭제",
    "모두 삭제",
    "폭파",
    "분해",
    "explode",
    "저장없이",
    "저장 없이",
    "닫기",
    "close",
)

HIGH_RISK_KEYWORDS = (
    "purge",
    "출력",
    "플롯",
    "plot",
    "일괄출력",
    "일괄 출력",
    "백업",
    "오류수정",
)

REVIEW_KEYWORDS = (
    "변경",
    "수정",
    "그리기",
    "만들기",
    "병합",
    "삽입",
    "rename",
    "merge",
    "change",
    "edit",
    "draw",
    "insert",
)


@dataclass(frozen=True)
class XiCADSafetyDecision:
    alias: str
    function: str
    description: str
    risk: str
    auto_run_allowed: bool
    reasons: tuple[str, ...]


def _upper(value: object) -> str:
    return str(value or "").strip().upper()


def _text(*values: object) -> str:
    return " ".join(str(v or "") for v in values).lower()


def classify_xicad_risk(alias: str, function: str = "", description: str = "") -> str:
    alias_u = _upper(alias)
    text = _text(alias, function, description)

    if alias_u in BLOCKED_ALIASES:
        return BLOCKED
    if any(keyword.lower() in text for keyword in BLOCKED_KEYWORDS):
        return BLOCKED
    if alias_u in HIGH_RISK_ALIASES:
        return HIGH_RISK
    if any(keyword.lower() in text for keyword in HIGH_RISK_KEYWORDS):
        return HIGH_RISK
    if any(keyword.lower() in text for keyword in REVIEW_KEYWORDS):
        return REVIEW_REQUIRED
    return INTERACTIVE_PREVIEW


def decide_xicad_safety(
    alias: str,
    function: str = "",
    description: str = "",
    *,
    recipe_verified: bool = False,
    recipe_scriptable: bool = False,
) -> XiCADSafetyDecision:
    risk = classify_xicad_risk(alias, function, description)
    reasons: list[str] = []

    if risk == BLOCKED:
        reasons.append("XiCAD command is blocked by alias or destructive keyword.")
    elif risk == HIGH_RISK:
        reasons.append("XiCAD command is high-risk and requires human review.")
    elif risk in {REVIEW_REQUIRED, INTERACTIVE_PREVIEW}:
        reasons.append("XiCAD command may be interactive or may mutate a drawing.")

    if not recipe_verified:
        reasons.append("No verified recipe exists.")
    if not recipe_scriptable:
        reasons.append("Recipe is not marked scriptable.")

    auto_run_allowed = bool(
        recipe_verified
        and recipe_scriptable
        and risk not in {BLOCKED, HIGH_RISK}
    )

    if not auto_run_allowed:
        reasons.append("Automatic execution is denied; keep as review-only plan.")

    return XiCADSafetyDecision(
        alias=_upper(alias),
        function=function,
        description=description,
        risk=risk,
        auto_run_allowed=auto_run_allowed,
        reasons=tuple(dict.fromkeys(reasons)),
    )


def max_risk(risks: Iterable[str]) -> str:
    result = SAFE_LOOKUP
    for risk in risks:
        if RISK_ORDER.get(risk, 0) > RISK_ORDER.get(result, 0):
            result = risk
    return result
