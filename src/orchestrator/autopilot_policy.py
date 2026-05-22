from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any


class AutopilotSafety(str, Enum):
    SAFE_TO_RUN = "SAFE_TO_RUN"
    HELD_FOR_REVIEW = "HELD_FOR_REVIEW"
    BLOCKED = "BLOCKED"


ALWAYS_HELD_KEYWORDS = (
    "--execute",
    "save_as",
    "delete_layer_objects",
    "purge",
    "explode",
    "sendcommand",
    "xicad-safe-run --execute",
    "run-command --execute",
)

SAFE_COMMAND_PREFIXES = (
    "hscad-tools",
    "hscad-tool-plan",
    "hscad-check-tools",
    "floorplan-analyze",
    "xicad-plan-generate",
    "xicad-plan-summary",
    "xicad-contract-plan",
    "xicad-contract-session",
    "xicad-contract-review-matrix",
    "xicad-contract-bundle-validate",
    "xicad-contract-review-pack",
    "xicad-contract-record-template",
    "xicad-contract-record-command",
)


@dataclass(frozen=True)
class AutopilotDecision:
    command: str
    safety: AutopilotSafety
    reason: str
    can_run: bool

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["safety"] = self.safety.value
        return data


def classify_autopilot_command(command: str) -> AutopilotDecision:
    normalized = command.lower().strip()

    if any(keyword in normalized for keyword in ALWAYS_HELD_KEYWORDS):
        return AutopilotDecision(command, AutopilotSafety.HELD_FOR_REVIEW, "Drawing mutation or execution-gated command.", False)

    if "recipe_registry" in normalized and ("write" in normalized or "modify" in normalized or "verified=true" in normalized):
        return AutopilotDecision(command, AutopilotSafety.BLOCKED, "Automatic recipe promotion is blocked.", False)

    if any(normalized.startswith(prefix) for prefix in SAFE_COMMAND_PREFIXES):
        return AutopilotDecision(command, AutopilotSafety.SAFE_TO_RUN, "Safe planning/reporting/file-output command.", True)

    if normalized.startswith("python -x utf8 -m neuro_seq_cad.app.cli analyze") and "--synthetic" in normalized:
        return AutopilotDecision(command, AutopilotSafety.SAFE_TO_RUN, "Synthetic neuro_seq_cad run creates files only.", True)

    if normalized.startswith("scan") or normalized.startswith("layers") or normalized.startswith("blocks") or normalized.startswith("texts") or normalized.startswith("analyze-architecture"):
        return AutopilotDecision(command, AutopilotSafety.SAFE_TO_RUN, "Read-only DWG inspection command.", True)

    return AutopilotDecision(command, AutopilotSafety.HELD_FOR_REVIEW, "Unknown command; review required before running.", False)
