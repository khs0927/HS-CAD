"""
opencv_lsd.py – OpenCV LSD(Line Segment Detector) 기반 선분 추출.

LSD 가 사용 불가능한 경우 HoughLinesP 로 자동 폴백.
추출된 선분에 대해 각도(angle)와 길이(length)를 계산하여 반환.
"""
from __future__ import annotations

import logging
import math
import uuid
from typing import Any

import numpy as np
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────────────
# OpenCV 임포트 (실패 시 더미 처리)
# ──────────────────────────────────────────────────────────────────────
try:
    import cv2

    _CV2_AVAILABLE = True
except ImportError:
    cv2 = None  # type: ignore[assignment]
    _CV2_AVAILABLE = False
    logger.warning("OpenCV(cv2)를 임포트할 수 없습니다. 선분 추출 비활성화.")


def _generate_id() -> str:
    return uuid.uuid4().hex[:8]


# ──────────────────────────────────────────────────────────────────────
# Pydantic Models
# ──────────────────────────────────────────────────────────────────────
class LineSegment(BaseModel):
    """단일 선분 결과.

    Attributes:
        id: 고유 식별자.
        p1: 시작점 [x1, y1].
        p2: 끝점 [x2, y2].
        angle: 수평축 기준 각도 (degree, -90 ~ 90).
        length: 선분의 유클리드 길이 (pixel 단위).
        confidence: 검출 신뢰도 (LSD: width, Hough: 1.0 고정).
        source: 검출 방법 식별 문자열.
    """

    id: str = Field(default_factory=_generate_id)
    p1: list[float] = Field(default_factory=lambda: [0.0, 0.0])
    p2: list[float] = Field(default_factory=lambda: [0.0, 0.0])
    angle: float = 0.0
    length: float = 0.0
    confidence: float = 1.0
    source: str = "opencv_lsd"

    @property
    def is_horizontal(self, tolerance_deg: float = 5.0) -> bool:
        """수평선 여부 판별 (±tolerance_deg 이내)."""
        return abs(self.angle) <= tolerance_deg or abs(abs(self.angle) - 180.0) <= tolerance_deg

    @property
    def is_vertical(self, tolerance_deg: float = 5.0) -> bool:
        """수직선 여부 판별 (±tolerance_deg 이내)."""
        return abs(abs(self.angle) - 90.0) <= tolerance_deg

    @property
    def midpoint(self) -> tuple[float, float]:
        """선분 중점 좌표."""
        return (
            (self.p1[0] + self.p2[0]) / 2.0,
            (self.p1[1] + self.p2[1]) / 2.0,
        )


class LineExtractionOutput(BaseModel):
    """선분 추출 전체 결과."""

    lines: list[LineSegment] = Field(default_factory=list)

    def filter_by_length(self, min_length: float = 0.0) -> list[LineSegment]:
        """최소 길이 이상의 선분만 필터링."""
        return [ln for ln in self.lines if ln.length >= min_length]

    @property
    def horizontal_lines(self) -> list[LineSegment]:
        return [ln for ln in self.lines if ln.is_horizontal]

    @property
    def vertical_lines(self) -> list[LineSegment]:
        return [ln for ln in self.lines if ln.is_vertical]


# ──────────────────────────────────────────────────────────────────────
# 수학 유틸리티
# ──────────────────────────────────────────────────────────────────────
def _compute_angle(x1: float, y1: float, x2: float, y2: float) -> float:
    """두 점 사이의 각도를 계산 (degree).

    # 수평축(x축) 기준으로 atan2를 사용하여 각도 산출.
    # 반환값 범위: -180 ~ 180 도.
    # θ = atan2(Δy, Δx) × (180/π)
    """
    dx = x2 - x1
    dy = y2 - y1
    # atan2(dy, dx) → 라디안 → 도(degree) 변환
    angle_rad = math.atan2(dy, dx)
    angle_deg = math.degrees(angle_rad)
    return angle_deg


def _compute_length(x1: float, y1: float, x2: float, y2: float) -> float:
    """두 점 사이의 유클리드 거리를 계산.

    # 거리 공식: L = √((x2-x1)² + (y2-y1)²)
    """
    dx = x2 - x1
    dy = y2 - y1
    return math.sqrt(dx * dx + dy * dy)


# ──────────────────────────────────────────────────────────────────────
# LSD 추출
# ──────────────────────────────────────────────────────────────────────
def _detect_lsd(gray: np.ndarray) -> list[LineSegment]:
    """OpenCV LSD 를 사용하여 선분 추출.

    # cv2.createLineSegmentDetector() 는 OpenCV 4.x 의 일부 빌드에서
    # 특허 문제로 비활성화될 수 있음. 그 경우 예외를 발생시킨다.
    """
    if cv2 is None:
        raise RuntimeError("OpenCV 미설치")

    try:
        lsd = cv2.createLineSegmentDetector(cv2.LSD_REFINE_STD)
    except AttributeError:
        raise RuntimeError(
            "cv2.createLineSegmentDetector 사용 불가 "
            "(OpenCV 빌드에서 LSD가 비활성화되었을 수 있음)"
        )

    lines_raw, widths, _, _ = lsd.detect(gray)

    if lines_raw is None:
        return []

    segments: list[LineSegment] = []
    # LSD 결과 형식: (N, 1, 4) – 각 행이 [x1, y1, x2, y2]
    for i, line in enumerate(lines_raw):
        x1, y1, x2, y2 = line[0]
        angle = _compute_angle(x1, y1, x2, y2)
        length = _compute_length(x1, y1, x2, y2)
        # LSD 의 width 값을 신뢰도 대용으로 사용
        conf = float(widths[i][0]) if widths is not None and i < len(widths) else 1.0

        segments.append(
            LineSegment(
                p1=[float(x1), float(y1)],
                p2=[float(x2), float(y2)],
                angle=angle,
                length=length,
                confidence=conf,
                source="opencv_lsd",
            )
        )

    return segments


# ──────────────────────────────────────────────────────────────────────
# HoughLinesP 폴백
# ──────────────────────────────────────────────────────────────────────
def _detect_hough_fallback(
    gray: np.ndarray,
    min_length: float = 30.0,
    max_gap: float = 10.0,
) -> list[LineSegment]:
    """HoughLinesP 를 사용한 선분 추출 (LSD 폴백).

    # Canny 에지 → HoughLinesP 파이프라인.
    # rho=1, theta=π/180, threshold=80 기본값.
    """
    if cv2 is None:
        raise RuntimeError("OpenCV 미설치")

    # Canny 에지 검출 – 임계값은 평면도 이미지에 최적화된 경험적 값
    edges = cv2.Canny(gray, 50, 150, apertureSize=3)

    lines_raw = cv2.HoughLinesP(
        edges,
        rho=1,
        theta=np.pi / 180,
        threshold=80,
        minLineLength=min_length,
        maxLineGap=max_gap,
    )

    if lines_raw is None:
        return []

    segments: list[LineSegment] = []
    for line in lines_raw:
        x1, y1, x2, y2 = line[0]
        angle = _compute_angle(float(x1), float(y1), float(x2), float(y2))
        length = _compute_length(float(x1), float(y1), float(x2), float(y2))

        segments.append(
            LineSegment(
                p1=[float(x1), float(y1)],
                p2=[float(x2), float(y2)],
                angle=angle,
                length=length,
                confidence=1.0,
                source="opencv_hough",
            )
        )

    return segments


# ──────────────────────────────────────────────────────────────────────
# 공개 API
# ──────────────────────────────────────────────────────────────────────
def extract_lines_lsd(
    binary_image: np.ndarray,
    min_length: float = 20.0,
) -> LineExtractionOutput:
    """이진 이미지에서 선분을 추출.

    LSD를 우선 시도하고, 실패 시 HoughLinesP로 자동 폴백한다.

    Args:
        binary_image: 그레이스케일 또는 이진화된 이미지 (numpy 배열).
            컬러 이미지가 입력되면 자동으로 그레이스케일 변환.
        min_length: 최소 선분 길이 (pixel).  이보다 짧은 선분은 제거.

    Returns:
        LineExtractionOutput – 추출된 선분 목록.
    """
    if not _CV2_AVAILABLE:
        logger.error("OpenCV 미설치 – 빈 결과 반환")
        return LineExtractionOutput()

    # 그레이스케일 변환 (필요 시)
    gray: np.ndarray
    if len(binary_image.shape) == 3:
        gray = cv2.cvtColor(binary_image, cv2.COLOR_BGR2GRAY)
    else:
        gray = binary_image.copy()

    # 1차 시도: LSD
    segments: list[LineSegment] = []
    try:
        segments = _detect_lsd(gray)
        logger.info("LSD 선분 검출 완료: %d 개", len(segments))
    except (RuntimeError, cv2.error) as exc:
        logger.warning("LSD 실패 (%s), HoughLinesP 폴백 사용", exc)
        try:
            segments = _detect_hough_fallback(gray, min_length=min_length)
            logger.info("HoughLinesP 폴백 완료: %d 개", len(segments))
        except Exception:
            logger.exception("HoughLinesP 폴백도 실패 – 빈 결과 반환")
            return LineExtractionOutput()

    # 최소 길이 필터링
    if min_length > 0:
        segments = [s for s in segments if s.length >= min_length]

    return LineExtractionOutput(lines=segments)
