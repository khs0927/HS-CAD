from __future__ import annotations

from dataclasses import dataclass


STANDARD_LAYERS = {
    "COL", "WAL1", "WAL2", "WAL3", "DOOR", "DOOR_ELE", "WIN", "WINBAR", "WINELE",
    "HAT", "HID", "ZONE", "SEC1", "SEC2", "FIN1", "FIN2", "TXT", "TXT1", "TXT2",
    "MEP", "NOTE", "STAIR", "DIM", "DIMLE", "CEN", "CEN1", "CEN2", "CEN3",
    "DEFPOINTS", "FIX", "FUR", "SYM", "SYM_T", "TIT", "AREA", "PARKING", "INS",
    "BOUND", "A-FORM", "MARK", "ELE", "ELE1", "ELE2", "ELE3", "ELE4",
    "ETC", "ETC1", "ETC2", "ETC3", "ETC4", "GRID", "GRID_BUB",
}

PROTECTED_LAYERS = {"0", "DEFPOINTS"}
DEFAULT_MIN_CONFIDENCE = 0.82
LAYER_ZERO_MIN_CONFIDENCE = 0.92


@dataclass(frozen=True)
class SafetyPolicy:
    save_forbidden: bool = True
    purge_delete_explode_forbidden: bool = True
    block_definition_edit_forbidden: bool = True
    raw_arbitrary_command_forbidden: bool = True
    layer_zero_default_blocked: bool = True
