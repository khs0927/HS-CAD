"""
normalize_scan.py — 스캔 도면 전처리 (Scan normalization pipeline)

처리 순서:
  1. 그레이스케일 변환 (Grayscale conversion)
  2. 적응적 이진화 (Otsu + Adaptive threshold)
  3. 모폴로지 노이즈 제거 (Morphological open/close)
  4. 기울기 보정 (Deskew via Hough transform)
  5. 콘텐츠 영역 크롭 (Crop to content area)

각 단계의 중간 결과를 debug 디렉토리에 저장하여 품질 검증이 가능합니다.
"""

from __future__ import annotations

import logging
import math
from pathlib import Path
from typing import Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# OpenCV 가져오기 (try/except fallback)
# ---------------------------------------------------------------------------
try:
    import cv2

    _HAS_CV2 = True
except ImportError:
    _HAS_CV2 = False
    logger.warning("cv2(opencv-python) 미설치 — 전처리 기능이 제한됩니다.")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def normalize_scan(
    image: np.ndarray,
    *,
    debug_dir: Optional[str | Path] = None,
    enable_deskew: bool = True,
    enable_crop: bool = True,
    morph_kernel_size: int = 3,
    adaptive_block_size: int = 31,
    adaptive_c: int = 10,
    crop_margin: int = 10,
    filename_prefix: str = "scan",
) -> np.ndarray:
    """스캔 도면 이미지를 전처리합니다.

    Args:
        image: 입력 이미지 (BGR 또는 그레이스케일, uint8).
        debug_dir: 중간 결과 저장 디렉토리 (None이면 저장 안 함).
        enable_deskew: 기울기 보정 수행 여부.
        enable_crop: 콘텐츠 영역 크롭 수행 여부.
        morph_kernel_size: 모폴로지 커널 크기 (홀수).
        adaptive_block_size: 적응적 이진화 블록 크기 (홀수, ≥3).
        adaptive_c: 적응적 이진화 상수 C.
        crop_margin: 크롭 시 여백 (px).
        filename_prefix: 디버그 이미지 파일명 접두사.

    Returns:
        전처리 완료된 이진 이미지 (uint8, 단일 채널).
    """
    if not _HAS_CV2:
        logger.warning("OpenCV 미설치 — 최소 전처리(NumPy)만 수행합니다.")
        return _fallback_normalize(image)

    # 디버그 디렉토리 생성
    save = debug_dir is not None
    if save:
        debug_path = Path(debug_dir)
        debug_path.mkdir(parents=True, exist_ok=True)

    # ── 1단계: 그레이스케일 변환 ──
    # 컬러 이미지(BGR 3채널)를 단일 채널 그레이스케일로 변환합니다.
    # 변환 공식: gray = 0.299R + 0.587G + 0.114B (BT.601 가중치)
    gray = _to_grayscale(image)
    if save:
        _save_debug(gray, debug_path, f"{filename_prefix}_01_grayscale")
    logger.debug("1단계 완료: 그레이스케일 변환 → shape=%s", gray.shape)

    # ── 2단계: 적응적 이진화 (Otsu + Adaptive Threshold) ──
    # 먼저 Otsu 방법으로 전역 최적 임계값을 구하고,
    # 그 후 적응적 이진화(가우시안 가중 평균)로 지역별 조명 차이를 보정합니다.
    # Otsu 이진화: 히스토그램의 클래스 간 분산을 최대화하는 임계값 T를 자동 선택
    binary = _adaptive_threshold(gray, adaptive_block_size, adaptive_c)
    if save:
        _save_debug(binary, debug_path, f"{filename_prefix}_02_threshold")
    logger.debug("2단계 완료: 적응적 이진화")

    # ── 3단계: 모폴로지 노이즈 제거 ──
    # Opening (침식→팽창): 작은 흰색 잡음 점 제거
    # Closing (팽창→침식): 작은 검은색 끊김 보정
    # 커널은 정사각형(예: 3×3)이며, 크기가 클수록 강한 필터링 효과
    cleaned = _morphological_clean(binary, morph_kernel_size)
    if save:
        _save_debug(cleaned, debug_path, f"{filename_prefix}_03_morphology")
    logger.debug("3단계 완료: 모폴로지 노이즈 제거 (kernel=%d)", morph_kernel_size)

    # ── 4단계: 기울기 보정 (Deskew) ──
    # 허프 변환으로 주요 직선을 검출하고, 이들의 각도 중앙값으로
    # 도면의 기울어진 정도(skew angle)를 추정하여 보정합니다.
    if enable_deskew:
        cleaned, skew_angle = _deskew(cleaned)
        if save:
            _save_debug(cleaned, debug_path, f"{filename_prefix}_04_deskew")
        logger.debug("4단계 완료: 기울기 보정 (skew=%.2f°)", skew_angle)
    else:
        logger.debug("4단계 건너뜀: 기울기 보정 비활성화")

    # ── 5단계: 콘텐츠 영역 크롭 ──
    # 이진 이미지에서 0이 아닌(검은색 선) 픽셀의 바운딩 박스를 구하고,
    # margin만큼 여유를 두고 크롭합니다.
    if enable_crop:
        cleaned = _crop_to_content(cleaned, margin=crop_margin)
        if save:
            _save_debug(cleaned, debug_path, f"{filename_prefix}_05_cropped")
        logger.debug("5단계 완료: 콘텐츠 영역 크롭 (margin=%d px)", crop_margin)
    else:
        logger.debug("5단계 건너뜀: 크롭 비활성화")

    logger.info(
        "전처리 완료: 최종 shape=%s, dtype=%s",
        cleaned.shape,
        cleaned.dtype,
    )
    return cleaned


# ---------------------------------------------------------------------------
# 내부 처리 함수 (Internal processing functions)
# ---------------------------------------------------------------------------

def _to_grayscale(image: np.ndarray) -> np.ndarray:
    """입력 이미지를 그레이스케일로 변환합니다.

    이미 단일 채널이면 그대로 반환합니다.
    BGR 3채널 → 그레이스케일 변환 공식:
      Y = 0.114 × B + 0.587 × G + 0.299 × R  (OpenCV BGR 순서)
    """
    if image.ndim == 2:
        return image.copy()
    if image.ndim == 3 and image.shape[2] == 1:
        return image[:, :, 0].copy()
    if image.ndim == 3 and image.shape[2] in (3, 4):
        return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    raise ValueError(f"예상하지 못한 이미지 shape: {image.shape}")


def _adaptive_threshold(
    gray: np.ndarray,
    block_size: int = 31,
    c: int = 10,
) -> np.ndarray:
    """Otsu + 적응적 가우시안 이진화를 수행합니다.

    처리 흐름:
      1. 가우시안 블러로 미세 노이즈 감소 (5×5 커널)
      2. Otsu 이진화로 전역 임계값 참고 (결과는 사용하지 않으나 로그 출력)
      3. 적응적 가우시안 이진화
         - 각 픽셀 주변 block_size × block_size 영역의 가우시안 가중 평균에서
           상수 C를 빼서 지역 임계값을 결정
         - 조명이 불균일한 스캔 이미지에 효과적
    """
    # 노이즈 저감을 위한 가우시안 블러
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)

    # Otsu 전역 임계값 (참고용 로그)
    otsu_val, _ = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    logger.debug("Otsu 전역 임계값: %.1f", otsu_val)

    # 적응적 가우시안 이진화
    # block_size는 반드시 홀수여야 하며, C는 평균에서 빼는 보정값
    if block_size % 2 == 0:
        block_size += 1
    if block_size < 3:
        block_size = 3

    binary = cv2.adaptiveThreshold(
        blurred,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        block_size,
        c,
    )
    return binary


def _morphological_clean(binary: np.ndarray, kernel_size: int = 3) -> np.ndarray:
    """모폴로지 연산으로 이진 이미지의 노이즈를 제거합니다.

    처리 흐름:
      1. Opening (열림 = 침식 → 팽창)
         - 구조체보다 작은 밝은 잡음 점(salt noise)을 제거
         - 벽선 같은 큰 구조는 보존
      2. Closing (닫힘 = 팽창 → 침식)
         - 선의 작은 끊김(gap)을 메워줌
         - 벽선의 연속성 복원에 효과적

    커널 크기가 클수록 강한 필터링이 적용되지만,
    너무 크면 세부 구조(문, 창문 표시)가 손상될 수 있으므로
    3~5 정도가 적절합니다.
    """
    if kernel_size % 2 == 0:
        kernel_size += 1

    # 정사각형 구조 요소 (structuring element)
    kernel = cv2.getStructuringElement(
        cv2.MORPH_RECT, (kernel_size, kernel_size)
    )

    # Opening: 작은 밝은 잡음 제거
    opened = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel, iterations=1)

    # Closing: 작은 끊김 보정
    closed = cv2.morphologyEx(opened, cv2.MORPH_CLOSE, kernel, iterations=1)

    return closed


def _deskew(binary: np.ndarray) -> Tuple[np.ndarray, float]:
    """허프 변환 기반 기울기 보정을 수행합니다.

    알고리즘:
      1. Canny 에지 검출로 선분 후보 추출
      2. 확률적 허프 변환(HoughLinesP)으로 선분 검출
      3. 각 선분의 수평 대비 각도를 계산:
           θ = arctan2(y2 − y1, x2 − x1) × (180 / π)
      4. 수평/수직에 가까운 선분들의 각도 중앙값(median)을 기울기(skew)로 사용
         - ±45° 범위의 선분만 사용 (대각선은 제외)
      5. 이미지 중심을 기준으로 회전 행렬 생성 후 어파인 변환으로 보정

    기울기가 매우 작으면(< 0.1°) 보정을 건너뛰어 불필요한 보간을 방지합니다.

    Returns:
        (보정된 이미지, 검출된 기울기 각도(°))
    """
    # 에지 검출 (Canny)
    edges = cv2.Canny(binary, 50, 150, apertureSize=3)

    # 확률적 허프 변환
    lines = cv2.HoughLinesP(
        edges,
        rho=1,
        theta=np.pi / 180,
        threshold=100,
        minLineLength=50,
        maxLineGap=10,
    )

    if lines is None or len(lines) == 0:
        logger.debug("허프 변환에서 선분을 검출하지 못했습니다. 기울기 보정 건너뜀.")
        return binary, 0.0

    # 각 선분의 각도 계산
    # θ = arctan2(Δy, Δx)를 도(°)로 변환
    angles: list[float] = []
    for line in lines:
        x1, y1, x2, y2 = line[0]
        dx = float(x2 - x1)
        dy = float(y2 - y1)

        if abs(dx) < 1e-6:
            # 거의 수직인 선분 → 각도 기여 없음 (수평 기울기만 보정)
            continue

        # arctan2로 각도 계산 (라디안 → 도)
        angle_deg = math.degrees(math.atan2(dy, dx))

        # ±45° 범위의 수평에 가까운 선분만 수집
        # (대각선이나 수직 선분은 기울기 추정에 부적합)
        if abs(angle_deg) <= 45.0:
            angles.append(angle_deg)

    if not angles:
        logger.debug("수평에 가까운 선분이 없습니다. 기울기 보정 건너뜀.")
        return binary, 0.0

    # 기울기 = 각도 중앙값
    # 중앙값(median)은 이상치(outlier)에 강건하여 평균(mean)보다 안정적
    skew_angle = float(np.median(angles))

    # 기울기가 매우 작으면 보정 불필요
    if abs(skew_angle) < 0.1:
        logger.debug("기울기 %.3f° — 보정 불필요", skew_angle)
        return binary, skew_angle

    # 회전 보정
    # 이미지 중심을 회전 중심으로 사용하여 잘리는 영역 최소화
    h, w = binary.shape[:2]
    center = (w / 2.0, h / 2.0)

    # 회전 행렬: 2×3 어파인 변환 행렬
    # getRotationMatrix2D(center, angle, scale)
    # angle > 0 → 반시계 방향 회전
    # 기울기를 상쇄하려면 −skew_angle 만큼 회전
    rotation_matrix = cv2.getRotationMatrix2D(center, -skew_angle, 1.0)

    # 어파인 변환 적용 (경계 밖은 흰색으로 채움 = 255)
    corrected = cv2.warpAffine(
        binary,
        rotation_matrix,
        (w, h),
        flags=cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=255,
    )

    logger.info("기울기 보정 적용: %.2f° 회전", -skew_angle)
    return corrected, skew_angle


def _crop_to_content(
    binary: np.ndarray,
    margin: int = 10,
    bg_value: int = 255,
) -> np.ndarray:
    """이진 이미지에서 콘텐츠(비배경) 영역만 크롭합니다.

    처리 흐름:
      1. 배경값(bg_value, 기본 255=흰색)이 아닌 픽셀 좌표를 수집
      2. 해당 좌표의 바운딩 박스 계산
      3. margin만큼 여유를 두고 크롭 (이미지 경계 클리핑)

    콘텐츠가 없으면(모두 배경) 원본을 그대로 반환합니다.
    """
    # 배경이 아닌 픽셀의 좌표 (row, col)
    if binary.ndim == 3:
        mask = np.any(binary != bg_value, axis=2)
    else:
        mask = binary != bg_value

    coords = np.argwhere(mask)

    if coords.size == 0:
        logger.warning("콘텐츠 픽셀이 없습니다. 크롭을 건너뜁니다.")
        return binary

    # 바운딩 박스: (min_row, min_col) ~ (max_row, max_col)
    r_min, c_min = coords.min(axis=0)
    r_max, c_max = coords.max(axis=0)

    h, w = binary.shape[:2]

    # 여백(margin) 적용 및 경계 클리핑
    r_min = max(0, r_min - margin)
    c_min = max(0, c_min - margin)
    r_max = min(h - 1, r_max + margin)
    c_max = min(w - 1, c_max + margin)

    cropped = binary[r_min : r_max + 1, c_min : c_max + 1]

    logger.debug(
        "크롭: (%d,%d)~(%d,%d) → shape=%s",
        c_min, r_min, c_max, r_max, cropped.shape,
    )
    return cropped.copy()


# ---------------------------------------------------------------------------
# 디버그 이미지 저장
# ---------------------------------------------------------------------------
def _save_debug(image: np.ndarray, debug_dir: Path, name: str) -> None:
    """중간 처리 결과를 디버그 디렉토리에 PNG로 저장합니다."""
    out_path = debug_dir / f"{name}.png"
    try:
        if _HAS_CV2:
            cv2.imwrite(str(out_path), image)
        else:
            # Pillow 폴백
            from PIL import Image as PILImage

            if image.ndim == 2:
                pil_img = PILImage.fromarray(image, mode="L")
            else:
                pil_img = PILImage.fromarray(image[:, :, ::-1], mode="RGB")
            pil_img.save(str(out_path))
        logger.debug("디버그 이미지 저장: %s", out_path)
    except Exception as exc:
        logger.warning("디버그 이미지 저장 실패: %s — %s", out_path, exc)


# ---------------------------------------------------------------------------
# OpenCV 없이 최소 전처리 (Fallback)
# ---------------------------------------------------------------------------
def _fallback_normalize(image: np.ndarray) -> np.ndarray:
    """OpenCV 없이 NumPy만으로 최소한의 전처리를 수행합니다.

    - 그레이스케일 변환 (BT.601 가중치)
    - 단순 전역 임계값 이진화 (threshold = 128)

    정확도는 OpenCV 파이프라인보다 낮지만,
    의존성 없이 기본적인 이진 이미지를 생성할 수 있습니다.
    """
    # 그레이스케일 변환
    if image.ndim == 3:
        # BT.601: Y = 0.299R + 0.587G + 0.114B
        # OpenCV는 BGR 순서이므로 가중치 순서 주의
        gray = np.dot(image[..., :3].astype(np.float32), [0.114, 0.587, 0.299])
        gray = gray.astype(np.uint8)
    elif image.ndim == 2:
        gray = image.copy()
    else:
        raise ValueError(f"예상하지 못한 이미지 shape: {image.shape}")

    # 단순 전역 임계값 이진화 (threshold = 128)
    binary = np.where(gray > 128, np.uint8(255), np.uint8(0))

    logger.info("Fallback 전처리 완료: shape=%s", binary.shape)
    return binary
