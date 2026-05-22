"""
mask_regions.py – 심볼 검출 영역 마스킹 유틸리티.

벽 선분 추출 전에 문, 창문, 텍스트 등의 검출 영역을 마스킹(채우기)하여
노이즈 간섭을 제거한다.
"""
from __future__ import annotations

import logging
from typing import Sequence

import numpy as np

from ..detection.symbol_schema import DetectionOutput, SymbolDetection

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────────────
# OpenCV 임포트 (선택적 – 마스킹은 numpy 만으로도 가능하지만
# cv2.rectangle 이 더 효율적)
# ──────────────────────────────────────────────────────────────────────
try:
    import cv2

    _CV2_AVAILABLE = True
except ImportError:
    cv2 = None  # type: ignore[assignment]
    _CV2_AVAILABLE = False
    logger.warning("OpenCV(cv2) 미설치 – numpy 기반 마스킹 사용.")


# ──────────────────────────────────────────────────────────────────────
# 공개 API
# ──────────────────────────────────────────────────────────────────────
def mask_symbol_regions(
    image: np.ndarray,
    detections: DetectionOutput,
    color: int | tuple[int, ...] = 255,
    padding: int = 0,
    types_to_mask: Sequence[str] | None = None,
) -> np.ndarray:
    """검출된 심볼 영역을 지정 색상으로 마스킹.

    문, 창문, 텍스트 등의 바운딩 박스 영역을 단색으로 채워서
    후속 벽 선분 추출 시 간섭을 줄인다.

    Args:
        image: 원본 이미지 (numpy 배열).  수정하지 않고 복사본을 반환.
        detections: 심볼 검출 결과 (DetectionOutput).
        color: 마스킹 색상.
            - 그레이스케일: int (예: 255 = 흰색).
            - 컬러(BGR): tuple (예: (255, 255, 255)).
        padding: 바운딩 박스를 양쪽으로 확장할 픽셀 수.
            벽 선과 겹치는 심볼 경계를 확실히 제거하기 위해 사용.
        types_to_mask: 마스킹할 심볼 타입 목록.
            None 이면 모든 타입을 마스킹.  예: ["door", "window", "text"]

    Returns:
        마스킹된 이미지 (원본과 동일한 shape/dtype).
    """
    # 원본 보존을 위해 복사
    masked = image.copy()
    h, w = masked.shape[:2]

    if not detections.symbols:
        logger.debug("마스킹할 심볼 없음 – 원본 이미지 그대로 반환")
        return masked

    mask_count = 0

    for sym in detections.symbols:
        # 타입 필터링
        if types_to_mask is not None and sym.type not in types_to_mask:
            continue

        # 바운딩 박스 좌표 추출 및 클리핑
        # bbox: [x1, y1, x2, y2] – 이미지 좌표계 (좌상단 원점, y 하향)
        if len(sym.bbox) < 4:
            continue

        x1 = max(0, int(sym.bbox[0]) - padding)
        y1 = max(0, int(sym.bbox[1]) - padding)
        x2 = min(w, int(sym.bbox[2]) + padding)
        y2 = min(h, int(sym.bbox[3]) + padding)

        if x2 <= x1 or y2 <= y1:
            continue

        # 영역 마스킹
        if _CV2_AVAILABLE:
            # cv2.rectangle 은 in-place 로 동작 – 이미 복사본이므로 안전
            fill_color: int | tuple[int, ...]
            if len(masked.shape) == 3:
                fill_color = color if isinstance(color, tuple) else (color, color, color)
            else:
                fill_color = color if isinstance(color, int) else color[0]  # type: ignore[index]
            cv2.rectangle(masked, (x1, y1), (x2, y2), fill_color, thickness=-1)
        else:
            # numpy 기반 마스킹 (OpenCV 없이도 동작)
            if len(masked.shape) == 3:
                if isinstance(color, int):
                    masked[y1:y2, x1:x2, :] = color
                else:
                    masked[y1:y2, x1:x2, :] = color
            else:
                fill_val = color if isinstance(color, int) else color[0]  # type: ignore[index]
                masked[y1:y2, x1:x2] = fill_val

        mask_count += 1

    logger.info(
        "심볼 마스킹 완료: %d개 영역 마스킹 (전체 %d개 중, 필터: %s)",
        mask_count,
        len(detections.symbols),
        types_to_mask or "전체",
    )

    return masked


def mask_bboxes(
    image: np.ndarray,
    bboxes: list[list[float]],
    color: int | tuple[int, ...] = 255,
    padding: int = 0,
) -> np.ndarray:
    """원시 바운딩 박스 리스트로 직접 마스킹 (DetectionOutput 없이 사용).

    Args:
        image: 원본 이미지.
        bboxes: [[x1, y1, x2, y2], ...] 형식의 바운딩 박스 리스트.
        color: 마스킹 색상.
        padding: 바운딩 박스 확장 픽셀 수.

    Returns:
        마스킹된 이미지.
    """
    # SymbolDetection 으로 변환 후 mask_symbol_regions 호출
    symbols = [
        SymbolDetection(
            type="unknown",
            bbox=[float(v) for v in bbox[:4]],
            source="manual",
        )
        for bbox in bboxes
        if len(bbox) >= 4
    ]
    det_output = DetectionOutput(symbols=symbols)
    return mask_symbol_regions(image, det_output, color=color, padding=padding)
