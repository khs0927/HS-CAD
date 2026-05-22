"""
schemas.py — VLM(Vision-Language Model) 피드백 및 도면 보정 스키마

VLM이 도면 원본 이미지와 AI 벡터화 결과를 비교 분석한 후 반환하는
구조화된 피드백(JSON)의 Pydantic 스키마 정의.
"""

from __future__ import annotations

from typing import Any, List, Literal

from pydantic import BaseModel, Field


class CorrectionInstruction(BaseModel):
    """VLM이 제시하는 개별 도면 객체 보정 지침."""

    target_entity_id: str = Field(
        ...,
        description="보정할 대상 EvidenceEntity ID. 신규 추가인 경우 'new'로 기재."
    )
    action: Literal["modify", "delete", "add", "none"] = Field(
        ...,
        description="취할 보정 조치 유형 — modify(수정), delete(삭제), add(신규 추가)"
    )
    element_type: str = Field(
        ...,
        description="대상 요소 종류 — wall | door | window | room | text | column | etc."
    )
    reason: str = Field(
        ...,
        description="보정이 필요한 이유 (예: '문 기호가 벽 바운더리 중심선에서 150mm 어긋남')"
    )
    description: str = Field(
        ...,
        description="보정 조치 세부 내역 설명"
    )
    # 보정에 필요한 추가 값들 (예: {"shift_x": 5.0, "shift_y": 0.0, "new_label": "Bedroom 1"})
    parameters: dict[str, Any] = Field(
        default_factory=dict,
        description="보정에 필요한 세부 파라미터 (좌표 이동값, 새로운 텍스트 등)"
    )


class VLMFloorplanRefinementOutput(BaseModel):
    """VLM 기반 도면 분석 및 일괄 보정 피드백 출력."""

    instructions: List[CorrectionInstruction] = Field(
        default_factory=list,
        description="각 요소별 보정 지침 목록"
    )
    global_notes: str = Field(
        "",
        description="도면 분석 총평 및 전체 레이아웃 관련 검토 보고"
    )
    quality_score: float = Field(
        1.0,
        ge=0.0,
        le=1.0,
        description="도면 품질 신뢰도 점수 (0.0 = 매우 불량, 1.0 = 완벽)"
    )
