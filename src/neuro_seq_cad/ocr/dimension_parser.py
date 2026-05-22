"""
dimension_parser.py — OCR 문자열로부터 치수 정보(Dimension) 정밀 파싱 및 구조화

도면 내에서 감지된 텍스트 중 실제 벽체나 문/창문 크기를 나타내는
자연수 치수값(예: "3,600", "L=1200", "W:900" 등)을 파싱하여 정밀 구조화된 데이터 형태로 제공합니다.
"""

from __future__ import annotations

import logging
import re
from typing import List, Tuple, Optional

from pydantic import BaseModel, Field
from neuro_seq_cad.geometry.primitives import BBox2D

logger = logging.getLogger(__name__)


class DimensionText(BaseModel):
    """도면에서 파싱된 정밀 치수 정보."""

    raw_text: str = Field(..., description="OCR이 읽어들인 원시 문자열")
    value: float = Field(..., description="추출된 치수 물리값 (mm 단위)")
    unit: str = Field("mm", description="물리 단위 (mm, m, 평, etc.)")
    bbox: BBox2D = Field(..., description="치수 텍스트 이미지 바운딩 박스")
    confidence: float = Field(1.0, description="OCR 인식 신뢰도")


def clean_dimension_string(text: str) -> str:
    """원시 치수 문자열에서 노이즈 문자 및 기호를 벗겨내고 숫자와 쉼표만 조립합니다.
    
    예: "L = 3,600 mm" -> "3600"
        "W: 900" -> "900"
    """
    text = text.strip()
    
    # 1. 괄호 제거
    text = re.sub(r"[\(\)\[\]\{\}]", "", text)
    
    # 2. 문자와 기호 접두사 제거 (L=, W=, H=, D=, CH= 등)
    # L=, W: 와 같이 숫자 앞에 붓는 형태 파싱
    prefix_match = re.search(r"(?:[a-zA-Z\s]{1,4}[=:]\s*)?([\d,]+)(?:\s*(?:mm|MM|m|M))?", text)
    if prefix_match:
        return prefix_match.group(1).replace(",", "")
        
    # 3. 쉼표(천단위 구분자) 및 모든 영문 단위 제거
    cleaned = re.sub(r"[^\d]", "", text)
    return cleaned


def parse_single_dimension(
    text: str,
    bbox: BBox2D,
    confidence: float = 1.0
) -> Optional[DimensionText]:
    """단일 OCR 텍스트 라인을 치수로 파싱합니다.
    
    건축 치수 규격(예: 100mm ~ 100,000mm)에 해당하는 경우 구조화된 DimensionText를 반환합니다.
    """
    cleaned = clean_dimension_string(text)
    if not cleaned:
        return None
        
    try:
        val = float(cleaned)
        # 건축 평면도에서 의미 있는 치수 한계 설정 (100mm ~ 100,000mm)
        # 100 미만의 치수는 스캔 노이즈(예: 1, I, o 등 문자 잔상)나 비건축 정보일 확률이 큼.
        if 100.0 <= val <= 100000.0:
            return DimensionText(
                raw_text=text,
                value=val,
                unit="mm",
                bbox=bbox,
                confidence=confidence
            )
    except ValueError:
        pass
        
    return None


def extract_dimensions(
    ocr_results: List[Tuple[BBox2D, str, float]]
) -> List[DimensionText]:
    """전체 OCR 인식 결과 집합에서 치수 관련 문자들만 선별하여 추출합니다."""
    dimensions: List[DimensionText] = []
    
    for bbox, text, conf in ocr_results:
        dim = parse_single_dimension(text, bbox, conf)
        if dim is not None:
            dimensions.append(dim)
            logger.debug(
                "치수 파싱 성공: '%s' -> %.1f mm (신뢰도: %.2f)",
                text, dim.value, conf
            )
            
    logger.info("치수 추출 완료: 총 %d개 텍스트 중 %d개 치수 감지", len(ocr_results), len(dimensions))
    return dimensions
