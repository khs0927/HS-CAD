"""
hough.py – HoughLinesP 기반 선분 추출 모듈.

opencv_lsd.py 의 LineSegment / LineExtractionOutput 스키마를 재사용하며,
HoughLinesP 의 파라미터를 세밀하게 제어할 수 있다.
"""
from __future__ import annotations

import logging
import math

import numpy as np

from .opencv_lsd import LineExtractionOutput, LineSegment

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────────────
# OpenCV 임포트
# ──────────────────────────────────────────────────────────────────────
try:
    import cv2

    _CV2_AVAILABLE = True
except ImportError:
    cv2 = None  # type: ignore[assignment]
    _CV2_AVAILABLE = False
    logger.warning("OpenCV(cv2) 미설치 – hough 선분 추출 비활성화.")


# ──────────────────────────────────────────────────────────────────────
# 수학 유틸 – 각도 및 길이 계산
# ──────────────────────────────────────────────────────────────────────
def _angle_deg(x1: float, y1: float, x2: float, y2: float) -> float:
    """두 점 사이의 각도를 계산 (degree).

    # θ = atan2(Δy, Δx) × (180/π)
    # 반환 범위: -180 ~ 180
    """
    return math.degrees(math.atan2(y2 - y1, x2 - x1))


def _euclidean_length(x1: float, y1: float, x2: float, y2: float) -> float:
    """유클리드 거리 계산.

    # L = √((x2-x1)² + (y2-y1)²)
    """
    dx = x2 - x1
    dy = y2 - y1
    return math.sqrt(dx * dx + dy * dy)


# ──────────────────────────────────────────────────────────────────────
# 공개 API
# ──────────────────────────────────────────────────────────────────────
def extract_lines_hough(
    binary_image: np.ndarray,
    min_length: float = 40.0,
    max_gap: float = 15.0,
    canny_low: int = 50,
    canny_high: int = 150,
    hough_threshold: int = 80,
) -> LineExtractionOutput:
    """HoughLinesP 를 사용하여 이진 이미지에서 선분을 추출.

    내부 처리 흐름:
      1. 컬러 이미지 → 그레이스케일 변환 (필요 시)
      2. Canny 에지 검출
      3. HoughLinesP 선분 검출
      4. 최소 길이(min_length) 미만 선분 제거
      5. 각 선분의 각도·길이 계산

    Args:
        binary_image: 입력 이미지 (그레이스케일 또는 컬러).
        min_length: 최소 선분 길이 (pixel).
        max_gap: 동일 선분으로 병합 가능한 최대 간격 (pixel).
        canny_low: Canny 하한 임계값.
        canny_high: Canny 상한 임계값.
        hough_threshold: HoughLinesP 누적기 임계값.

    Returns:
        LineExtractionOutput – 검출된 선분 리스트.
    """
    if not _CV2_AVAILABLE:
        logger.error("OpenCV 미설치 – 빈 결과 반환")
        return LineExtractionOutput()

    # 그레이스케일 변환
    if len(binary_image.shape) == 3:
        gray = cv2.cvtColor(binary_image, cv2.COLOR_BGR2GRAY)
    else:
        gray = binary_image.copy()

    # Canny 에지 검출
    # Canny 알고리즘: Sobel 그래디언트 → 비최대억제 → 이중 임계 이력추적
    edges = cv2.Canny(gray, canny_low, canny_high, apertureSize=3)

    # HoughLinesP 확률적 허프 변환
    # rho: 거리 해상도 (1 pixel)
    # theta: 각도 해상도 (π/180 rad = 1°)
    lines_raw = cv2.HoughLinesP(
        edges,
        rho=1,
        theta=np.pi / 180.0,
        threshold=hough_threshold,
        minLineLength=min_length,
        maxLineGap=max_gap,
    )

    if lines_raw is None:
        logger.info("HoughLinesP: 선분 0개 검출")
        return LineExtractionOutput()

    segments: list[LineSegment] = []
    for line in lines_raw:
        x1, y1, x2, y2 = (float(v) for v in line[0])

        length = _euclidean_length(x1, y1, x2, y2)
        # 최소 길이 필터 (HoughLinesP 자체에도 minLineLength 있지만 이중 체크)
        if length < min_length:
            continue

        angle = _angle_deg(x1, y1, x2, y2)

        segments.append(
            LineSegment(
                p1=[x1, y1],
                p2=[x2, y2],
                angle=angle,
                length=length,
                confidence=1.0,
                source="opencv_hough",
            )
        )

    logger.info("HoughLinesP: 선분 %d개 검출 (min_length=%.1f)", len(segments), min_length)
    return LineExtractionOutput(lines=segments)
