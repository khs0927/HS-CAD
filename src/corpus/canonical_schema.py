"""Canonical architecture schema.

Defines the set of *canonical elements* and *situation tags* that are used as a
neutral representation of drawing content.  All external corpus extraction
converts raw data into these generic concepts before any company‑specific
mapping is applied.
"""

from __future__ import annotations

from enum import Enum
from typing import List


class CanonicalElement(str, Enum):
    WALL = "WALL"
    COLUMN = "COLUMN"
    BEAM = "BEAM"
    SLAB = "SLAB"
    DOOR = "DOOR"
    WINDOW = "WINDOW"
    STAIR = "STAIR"
    RAMP = "RAMP"
    ELEVATOR = "ELEVATOR"
    TOILET = "TOILET"
    ROOM_NAME = "ROOM_NAME"
    DIMENSION = "DIMENSION"
    GRID = "GRID"
    CENTERLINE = "CENTERLINE"
    SECTION_MARK = "SECTION_MARK"
    ELEVATION_MARK = "ELEVATION_MARK"
    DETAIL_MARK = "DETAIL_MARK"
    TITLE_BLOCK = "TITLE_BLOCK"
    MATERIAL_NOTE = "MATERIAL_NOTE"
    FINISH_NOTE = "FINISH_NOTE"
    FIRE_SAFETY = "FIRE_SAFETY"
    ACOUSTIC = "ACOUSTIC"
    THERMAL_INSULATION = "THERMAL_INSULATION"
    WATERPROOFING = "WATERPROOFING"
    STRUCTURAL_STEEL = "STRUCTURAL_STEEL"
    PANEL_SYSTEM = "PANEL_SYSTEM"
    CEILING_SYSTEM = "CEILING_SYSTEM"
    FLOOR_FINISH = "FLOOR_FINISH"
    UNKNOWN = "UNKNOWN"


class SituationTag(str, Enum):
    SOUND_PROOFING_DOOR = "방음문"
    SOUND_PROOFING_WINDOW = "방음시창"
    PROJECT_WINDOW = "프로젝트창"
    FIRE_ACCESS = "소방관진입창"
    FIRE_PAINT = "내화도장"
    PANEL_FINISH = "판넬마감"
    H_BEAM_CONNECTION = "H빔접합"
    EXTERNAL_WALL_DETAIL = "외벽상세"
    WINDOW_DETAIL = "창호상세"
    DOOR_DETAIL = "문상세"
    CEILING_FINISH = "천장마감"
    LIGHT_GIRDER_CEILING = "경량철골천장"
    GYPSUM_TEX = "석고텍스"
    FIRE_PARTITION = "방화구획"
    ACCESSIBLE_FACILITY = "장애인편의시설"
    ACADEMY_REUSE = "학원용도변경"
    EVACUATION_STAIR = "피난계단"
    RESTROOM_DETAIL = "화장실상세"
    EXTERNAL_INSULATION = "외단열"
    WATERPROOF_DETAIL = "방수상세"
    ROOF_DETAIL = "지붕상세"
    RAILING_DETAIL = "난간상세"
    UNKNOWN = "unknown"

# Helper lists for easy iteration
CANONICAL_ELEMENTS: List[CanonicalElement] = list(CanonicalElement)
SITUATION_TAGS: List[SituationTag] = list(SituationTag)
