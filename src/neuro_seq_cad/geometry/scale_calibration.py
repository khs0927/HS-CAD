"""
scale_calibration.py — OCR 치수 텍스트와 도면 선분을 매칭하여 실제 스케일(Scale Factor) 보정

이미지 상의 픽셀 거리(px)와 OCR이 감지한 치수 텍스트(mm)를 비교하여,
1픽셀이 몇 mm에 해당하는지 나타내는 scale_factor (mm/px)를 자동으로 추정합니다.
이상치(Outlier)에 강인한 중앙값(Median) 추정 방식을 적용합니다.
"""

from __future__ import annotations

import logging
import re
from typing import List, Tuple

import numpy as np
from pydantic import BaseModel, Field

from neuro_seq_cad.geometry.primitives import Line2D, BBox2D

logger = logging.getLogger(__name__)


class ScaleCandidate(BaseModel):
    """치수 텍스트와 선분 매칭을 통해 생성된 스케일 후보."""

    text: str
    parsed_value: float  # 물리 거리 (mm)
    pixel_length: float  # 픽셀 거리 (px)
    scale_factor: float  # mm / px
    distance_to_text: float  # 텍스트와 선분 사이의 거리


class ScaleCalibrationResult(BaseModel):
    """스케일 보정 최종 결과."""

    scale_factor: float = Field(..., description="추정된 픽셀당 mm 스케일 팩터 (mm/px)")
    confidence: float = Field(..., description="신뢰도 점수 (0.0 ~ 1.0)")
    num_matches: int = Field(..., description="매칭된 유효 후보 개수")
    candidates: List[float] = Field(default_factory=list, description="유효한 스케일 후보값 목록")


def parse_dimension_value(text: str) -> float | None:
    """OCR 감지 텍스트에서 순수 숫자 치수 값을 파싱합니다.
    
    예: "3,600" -> 3600.0, "1200" -> 1200.0, "L=450" -> 450.0
    방 단위(m2, 평)나 문자열이 섞인 노이즈는 제외하고 건축 치수 단위인 100~50000 범위의 자연수를 매칭합니다.
    """
    # 숫자와 쉼표만 남김
    cleaned = re.sub(r"[^\d]", "", text)
    if not cleaned:
        return None
        
    try:
        val = float(cleaned)
        # 건축 평면도 치수는 통상 mm 단위이며 100mm ~ 100000mm 범위에 위치함.
        # 너무 작은 값(예: 1~10px 노이즈)이나 극단적인 값은 스케일 매칭에서 배제
        if 100.0 <= val <= 100000.0:
            return val
    except ValueError:
        pass
        
    return None


def calibrate_scale(
    lines: List[Line2D],
    ocr_results: List[Tuple[BBox2D, str]],
    default_scale: float = 1.0,
    max_text_to_line_dist: float = 50.0
) -> ScaleCalibrationResult:
    """OCR 치수 문자와 도면 선분을 매칭하여 최적의 scale_factor를 도출합니다.

    알고리즘 흐름:
    1. OCR 텍스트 목록에서 유효한 숫자 치수(mm)를 파싱합니다.
    2. 각 치수 텍스트 주변(max_text_to_line_dist 이내)에 존재하고, 텍스트 방향과 유사한 선분을 검색합니다.
    3. 치수값(mm) / 선분의 픽셀 길이(px)를 계산하여 scale_factor 후보들을 생성합니다.
    4. 후보군의 Median을 구하여 노이즈(오인식된 텍스트 및 잘못 연결된 선분)를 제거하고 최종 scale_factor를 결정합니다.
    5. 후보들의 분산 및 매칭 개수를 기반으로 신뢰도(confidence)를 부여합니다.

    Args:
        lines: 도면에서 검출된 선분 리스트 (Line2D, 치수 보조선 또는 치수선)
        ocr_results: OCR 검출 결과 [(BBox2D, 텍스트 문자열)]
        default_scale: 매칭 실패 시 사용할 기본 스케일 값
        max_text_to_line_dist: 텍스트 박스와 매칭할 선분 간의 최대 거리 (px)

    Returns:
        ScaleCalibrationResult
    """
    candidates: List[ScaleCandidate] = []
    
    for bbox, text in ocr_results:
        real_val = parse_dimension_value(text)
        if real_val is None:
            continue
            
        text_center = bbox.center()
        text_w = bbox.width()
        text_h = bbox.height()
        
        # 텍스트가 대략 가로 쓰기인지 세로 쓰기인지 판단
        is_text_horizontal = text_w >= text_h
        
        # 이 텍스트와 매칭될 가능성이 높은 선분 탐색
        best_line: Line2D | None = None
        min_dist = float("inf")
        
        for line in lines:
            line_len = line.length()
            if line_len < 10.0:  # 너무 짧은 선분은 노이즈로 배제
                continue
                
            # 선분의 수평/수직 여부
            dx, dy = line.direction()
            is_line_horizontal = abs(dx) > abs(dy)
            
            # 텍스트 방향과 선분 방향이 일치해야 함 (가로 텍스트는 가로 선분과, 세로 텍스트는 세로 선분과 매칭)
            if is_text_horizontal != is_line_horizontal:
                continue
                
            # 텍스트 중심에서 선분까지의 거리 측정
            dist = line.point_distance(text_center)
            
            # 텍스트 bbox 영역과 선분 투영 범위가 겹치는지 체크
            t = line.project_point(text_center)
            # 선분 연장선 상이 아닌 실제 선분 부근에 정사영되어야 함 (-0.2 ~ 1.2 범위)
            if -0.2 <= t <= 1.2:
                if dist < min_dist:
                    min_dist = dist
                    best_line = line
                    
        # 유효 범위 내에 매칭된 선분이 있는 경우 후보군 추가
        if best_line is not None and min_dist <= max_text_to_line_dist:
            px_len = best_line.length()
            s_factor = real_val / px_len
            
            # 비정상적인 스케일값 필터링 (예: 1px당 0.1mm 이하 또는 200mm 이상은 현실적인 스캔 해상도가 아님)
            if 0.5 <= s_factor <= 100.0:
                candidates.append(ScaleCandidate(
                    text=text,
                    parsed_value=real_val,
                    pixel_length=px_len,
                    scale_factor=s_factor,
                    distance_to_text=min_dist
                ))
                logger.debug(
                    "스케일 후보 등록: '%s' -> %dmm, 선분=%.1fpx, scale=%.3f mm/px (거리=%.1fpx)",
                    text, real_val, px_len, s_factor, min_dist
                )
                
    if not candidates:
        logger.warning("스케일 자동 매칭 실패. 기본 스케일(%.3f)을 사용합니다.", default_scale)
        return ScaleCalibrationResult(
            scale_factor=default_scale,
            confidence=0.0,
            num_matches=0,
            candidates=[]
        )
        
    # 이상치 배제를 위해 후보 스케일 팩터 추출 후 Median 계산
    s_factors = [c.scale_factor for c in candidates]
    median_scale = float(np.median(s_factors))
    
    # 신뢰도(Confidence) 계산
    # 1. 매칭 후보 수 가중치
    num_matches = len(candidates)
    if num_matches >= 5:
        count_score = 0.6
    elif num_matches >= 3:
        count_score = 0.5
    else:
        count_score = 0.3
        
    # 2. 후보값들의 일치성(편차) 가중치
    # 편차가 작을수록 높은 신뢰도 부여
    std_dev = float(np.std(s_factors))
    mean_val = float(np.mean(s_factors))
    cv = std_dev / mean_val if mean_val > 0 else 1.0  # 변동계수
    
    if cv < 0.05:
        consistency_score = 0.4
    elif cv < 0.15:
        consistency_score = 0.3
    elif cv < 0.30:
        consistency_score = 0.15
    else:
        consistency_score = 0.05
        
    confidence = count_score + consistency_score
    confidence = min(1.0, max(0.0, confidence))
    
    logger.info(
        "스케일 보정 완료: scale_factor=%.4f mm/px, 신뢰도=%.2f (매칭수=%d, 변동계수=%.2f%%)",
        median_scale, confidence, num_matches, cv * 100
    )
    
    return ScaleCalibrationResult(
        scale_factor=median_scale,
        confidence=confidence,
        num_matches=num_matches,
        candidates=s_factors
    )
