from __future__ import annotations

from dataclasses import asdict, dataclass

try:
    from enum import StrEnum
except ImportError:
    from enum import Enum

    class StrEnum(str, Enum):
        pass


class SafetyClass(StrEnum):
    SAFE_READ_ONLY = "safe_read_only"
    SAFE_FILE_OUTPUT = "safe_file_output"
    REVIEW_GATED = "review_gated"
    BLOCKED = "blocked"


_MUTATION_TOKENS = (
    "--execute",
    "save_as",
    "save-as",
    "delete",
    "purge",
    "explode",
    "erase",
    "삭제",
    "저장",
    "분해",
)


@dataclass(frozen=True)
class StepSafety:
    command: str
    safety_class: SafetyClass
    safe_to_run: bool
    reason: str

    def to_dict(self) -> dict:
        data = asdict(self)
        data["safety_class"] = self.safety_class.value
        return data


def classify_command_safety(command: str, *, wants_write: bool = False) -> StepSafety:
    cmd = command.lower().strip()

    if any(token in cmd for token in _MUTATION_TOKENS):
        return StepSafety(command, SafetyClass.BLOCKED, False, "Mutation or destructive token detected.")

    if wants_write and any(token in cmd for token in ("run-command", "xicad-safe-run")):
        return StepSafety(command, SafetyClass.REVIEW_GATED, False, "Write intent requires human review and SaveAs.")

    if any(
        token in cmd
        for token in (
            "scan",
            "layers",
            "blocks",
            "texts",
            "quantity",
            "analyze-architecture",
            "detect-xicad",
            "hscad-tools",
            "hscad-tool-plan",
            "xicad-safe-catalog",
            "xicad-safe-plan",
        )
    ):
        return StepSafety(command, SafetyClass.SAFE_READ_ONLY, True, "Read-only or planning command.")

    if "floorplan-analyze" in cmd or "neuro_seq_cad" in cmd:
        return StepSafety(command, SafetyClass.SAFE_FILE_OUTPUT, True, "Creates output files without editing a DWG.")

    if "setup_third_party" in cmd or "download_raster2seq" in cmd:
        return StepSafety(command, SafetyClass.REVIEW_GATED, False, "Environment setup is not auto-run by the agent.")

    return StepSafety(command, SafetyClass.REVIEW_GATED, False, "Unknown command requires review.")
