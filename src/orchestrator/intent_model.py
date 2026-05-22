from __future__ import annotations

try:
    from enum import StrEnum
except ImportError:  # Python < 3.11 fallback
    from enum import Enum
    class StrEnum(str, Enum):
        pass

from .agent_state import TaskContext


class AgentIntent(StrEnum):
    FLOORPLAN_TO_CAD = "floorplan_to_cad"
    FLOORPLAN_TO_ACTIVE_DWG = "floorplan_to_active_dwg"
    DWG_INSPECTION = "dwg_inspection"
    DWG_CHANGE_REVIEW_FIRST = "dwg_change_review_first"
    XICAD_ARCH_DRAW = "xicad_arch_draw"
    XICAD_LAYER_MANAGE = "xicad_layer_manage"
    XICAD_AREA_CALC = "xicad_area_calc"
    XICAD_TEXT_DIM = "xicad_text_dim"
    HYBRID_STEEL_WORKFLOW = "hybrid_steel_workflow"
    GENERAL_SAFE_INSPECTION = "general_safe_inspection"


def classify_agent_intent(context: TaskContext) -> AgentIntent:
    text = context.task.lower()

    if context.has_image:
        if context.has_active_drawing or context.dwg_path or "dwg" in text or "zwcad" in text:
            return AgentIntent.FLOORPLAN_TO_ACTIVE_DWG
        return AgentIntent.FLOORPLAN_TO_CAD
    if context.has_dwg and context.wants_write:
        return AgentIntent.DWG_CHANGE_REVIEW_FIRST
    if context.has_dwg:
        return AgentIntent.DWG_INSPECTION

    if any(token in text for token in ("면적", "수량", "물량", "area", "quantity")):
        return AgentIntent.XICAD_AREA_CALC
    if any(token in text for token in ("레이어", "layer", "색상", "병합", "켜기", "끄기")):
        return AgentIntent.XICAD_LAYER_MANAGE
    if any(token in text for token in ("문자", "텍스트", "치수", "dimension", "text")):
        return AgentIntent.XICAD_TEXT_DIM
    if context.wants_steel:
        return AgentIntent.HYBRID_STEEL_WORKFLOW
    if context.wants_xicad and any(token in text for token in ("벽체", "문", "창", "계단", "주차", "난간")):
        return AgentIntent.XICAD_ARCH_DRAW

    if any(token in text for token in ("면적", "구적", "실별", "수량", "표")):
        return AgentIntent.XICAD_AREA_CALC
    if any(token in text for token in ("레이어", "켜", "layer", "색상", "병합", "끄기", "켜기")):
        return AgentIntent.XICAD_LAYER_MANAGE
    if any(token in text for token in ("문자", "텍스트", "치수", "dimension", "text")):
        return AgentIntent.XICAD_TEXT_DIM
    if context.wants_steel:
        return AgentIntent.HYBRID_STEEL_WORKFLOW
    if context.wants_xicad and any(token in text for token in ("벽체", "단열", "문", "창", "계단", "주차", "엘리베이터")):
        return AgentIntent.XICAD_ARCH_DRAW
    if context.has_image:
        if context.has_dwg or context.has_active_drawing or "삽입" in text:
            return AgentIntent.FLOORPLAN_TO_ACTIVE_DWG
        return AgentIntent.FLOORPLAN_TO_CAD
    if context.has_dwg and context.wants_write:
        return AgentIntent.DWG_CHANGE_REVIEW_FIRST
    if context.has_dwg:
        return AgentIntent.DWG_INSPECTION
    return AgentIntent.GENERAL_SAFE_INSPECTION
