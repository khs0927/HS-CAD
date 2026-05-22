"""
image_loader.py — 도면 이미지 로딩 및 합성 테스트 도면 생성

지원 포맷: JPG, PNG, BMP, TIFF, PDF (첫 페이지)
PDF 지원 우선순위: PyMuPDF(fitz) → Pillow
모델/파일이 없을 때 테스트용 합성 도면 생성 기능 포함.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional, Union

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
    logger.warning("cv2(opencv-python) 미설치 — 이미지 로딩 기능이 제한됩니다.")


# ---------------------------------------------------------------------------
# 지원 확장자
# ---------------------------------------------------------------------------
_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".tif"}
_PDF_EXTENSIONS = {".pdf"}
_ALL_EXTENSIONS = _IMAGE_EXTENSIONS | _PDF_EXTENSIONS


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def load_image(
    path: Union[str, Path],
    *,
    target_size: Optional[int] = None,
    grayscale: bool = False,
) -> np.ndarray:
    """도면 이미지를 BGR NumPy 배열로 로드합니다.

    Args:
        path: 이미지 또는 PDF 파일 경로.
        target_size: 장축 기준 리사이즈 크기 (px). None이면 원본 크기 유지.
        grayscale: True이면 그레이스케일로 로드 (단일 채널).

    Returns:
        np.ndarray — BGR (H, W, 3) 또는 그레이스케일 (H, W) 배열.

    Raises:
        FileNotFoundError: 파일이 존재하지 않을 때.
        ValueError: 지원하지 않는 확장자일 때.
        RuntimeError: 이미지 디코딩에 실패했을 때.
    """
    path = Path(path).resolve()

    if not path.exists():
        raise FileNotFoundError(f"파일을 찾을 수 없습니다: {path}")

    ext = path.suffix.lower()
    if ext not in _ALL_EXTENSIONS:
        raise ValueError(
            f"지원하지 않는 확장자입니다: '{ext}'. "
            f"지원 형식: {sorted(_ALL_EXTENSIONS)}"
        )

    # ── PDF 로딩 ──
    if ext in _PDF_EXTENSIONS:
        image = _load_pdf_first_page(path)
    else:
        # ── 래스터 이미지 로딩 ──
        image = _load_raster_image(path, grayscale=grayscale)

    if image is None:
        raise RuntimeError(f"이미지 디코딩 실패: {path}")

    # ── 그레이스케일 변환 (PDF 로딩 시 BGR로 반환되므로 별도 처리) ──
    if grayscale and image.ndim == 3:
        if not _HAS_CV2:
            # numpy 기반 단순 그레이스케일 변환 (BT.601 가중치)
            image = np.dot(image[..., :3], [0.114, 0.587, 0.299]).astype(np.uint8)
        else:
            image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    # ── 리사이즈 ──
    if target_size is not None:
        image = _resize_long_edge(image, target_size)

    logger.info(
        "이미지 로드 완료: %s → shape=%s, dtype=%s",
        path.name,
        image.shape,
        image.dtype,
    )
    return image


def generate_synthetic_floorplan(
    width: int = 800,
    height: int = 600,
    *,
    wall_thickness: int = 8,
    margin: int = 60,
) -> np.ndarray:
    """테스트/데모용 합성 평면도 이미지를 생성합니다.

    생성 구조:
      - 외벽: 사각형 (margin 안쪽)
      - 내벽: 가로 칸막이 1개
      - 문: 왼쪽 하단 방에 개구부 (door opening)
      - 창문: 상단 벽에 이중선 표시

    Args:
        width: 이미지 너비 (px).
        height: 이미지 높이 (px).
        wall_thickness: 벽 두께 (px).
        margin: 외벽 여백 (px).

    Returns:
        np.ndarray — BGR (H, W, 3) 합성 도면 이미지.
    """
    if not _HAS_CV2:
        # OpenCV 없이 NumPy만으로 간단한 합성 생성
        return _generate_synthetic_numpy(width, height, wall_thickness, margin)

    # 흰색 배경
    canvas = np.ones((height, width, 3), dtype=np.uint8) * 255

    # ── 좌표 계산 ──
    x1, y1 = margin, margin                       # 외벽 왼쪽 상단
    x2, y2 = width - margin, height - margin       # 외벽 오른쪽 하단
    mid_y = (y1 + y2) // 2                         # 가로 내벽 Y 위치
    wt = wall_thickness

    # ── 외벽 (4면) ──
    # 상단 벽
    cv2.rectangle(canvas, (x1, y1), (x2, y1 + wt), (0, 0, 0), -1)
    # 하단 벽
    cv2.rectangle(canvas, (x1, y2 - wt), (x2, y2), (0, 0, 0), -1)
    # 좌측 벽
    cv2.rectangle(canvas, (x1, y1), (x1 + wt, y2), (0, 0, 0), -1)
    # 우측 벽
    cv2.rectangle(canvas, (x2 - wt, y1), (x2, y2), (0, 0, 0), -1)

    # ── 내부 가로 칸막이벽 ──
    cv2.rectangle(canvas, (x1, mid_y - wt // 2), (x2, mid_y + wt // 2), (0, 0, 0), -1)

    # ── 문 개구부 (하단 방 왼쪽 벽) ──
    door_w = 50
    door_y_start = mid_y + 30
    door_y_end = door_y_start + door_w
    # 벽 지우기 (흰색으로 덮기)
    cv2.rectangle(
        canvas,
        (x1, door_y_start),
        (x1 + wt, door_y_end),
        (255, 255, 255),
        -1,
    )
    # 문 스윙 아크 (1/4 원호)
    cv2.ellipse(
        canvas,
        (x1 + wt, door_y_start),
        (door_w, door_w),
        0,
        0,
        90,
        (0, 0, 200),       # 빨간색 아크
        1,
        cv2.LINE_AA,
    )

    # ── 창문 표시 (상단 벽 중앙) ──
    win_w = 80
    win_cx = (x1 + x2) // 2
    win_x1 = win_cx - win_w // 2
    win_x2 = win_cx + win_w // 2
    # 벽 지우기
    cv2.rectangle(
        canvas,
        (win_x1, y1),
        (win_x2, y1 + wt),
        (255, 255, 255),
        -1,
    )
    # 이중선 (창문 프레임)
    cv2.line(canvas, (win_x1, y1 + 2), (win_x2, y1 + 2), (200, 0, 0), 1, cv2.LINE_AA)
    cv2.line(
        canvas, (win_x1, y1 + wt - 2), (win_x2, y1 + wt - 2), (200, 0, 0), 1, cv2.LINE_AA
    )

    # ── 방 이름 텍스트 ──
    font = cv2.FONT_HERSHEY_SIMPLEX
    cv2.putText(
        canvas,
        "Room A",
        (x1 + 30, (y1 + mid_y) // 2 + 10),
        font,
        0.6,
        (100, 100, 100),
        1,
        cv2.LINE_AA,
    )
    cv2.putText(
        canvas,
        "Room B",
        (x1 + 30, (mid_y + y2) // 2 + 10),
        font,
        0.6,
        (100, 100, 100),
        1,
        cv2.LINE_AA,
    )

    logger.info("합성 평면도 생성 완료: %dx%d px", width, height)
    return canvas


# ---------------------------------------------------------------------------
# 내부 헬퍼 함수 (Internal helpers)
# ---------------------------------------------------------------------------
def _load_raster_image(path: Path, *, grayscale: bool = False) -> Optional[np.ndarray]:
    """OpenCV로 래스터 이미지 로드. 실패 시 Pillow 폴백."""
    if _HAS_CV2:
        flags = cv2.IMREAD_GRAYSCALE if grayscale else cv2.IMREAD_COLOR
        img = cv2.imread(str(path), flags)
        if img is not None:
            return img
        logger.warning("cv2.imread 실패, Pillow 폴백 시도: %s", path.name)

    # Pillow 폴백
    return _load_with_pillow(path, grayscale=grayscale)


def _load_with_pillow(path: Path, *, grayscale: bool = False) -> Optional[np.ndarray]:
    """Pillow로 이미지 로드 → NumPy 배열 (BGR) 변환."""
    try:
        from PIL import Image as PILImage
    except ImportError:
        logger.error("Pillow(PIL) 미설치 — 이미지를 로드할 수 없습니다.")
        return None

    try:
        pil_img = PILImage.open(path)
        if grayscale:
            pil_img = pil_img.convert("L")
            return np.array(pil_img, dtype=np.uint8)
        else:
            pil_img = pil_img.convert("RGB")
            arr = np.array(pil_img, dtype=np.uint8)
            # RGB → BGR (OpenCV 호환)
            return arr[:, :, ::-1].copy()
    except Exception as exc:
        logger.error("Pillow 이미지 로딩 실패: %s — %s", path.name, exc)
        return None


def _load_pdf_first_page(path: Path, dpi: int = 200) -> Optional[np.ndarray]:
    """PDF 첫 페이지를 이미지로 렌더링합니다.

    우선순위:
      1. PyMuPDF (fitz) — 빠르고 고품질
      2. Pillow — pdf2image가 없을 경우 제한적 지원

    Args:
        path: PDF 파일 경로.
        dpi: 렌더링 해상도 (기본 200 DPI).

    Returns:
        BGR (H, W, 3) NumPy 배열 또는 None.
    """
    # ── 방법 1: PyMuPDF (fitz) ──
    try:
        import fitz  # PyMuPDF

        pdf_doc = fitz.open(str(path))
        if len(pdf_doc) == 0:
            logger.error("PDF에 페이지가 없습니다: %s", path.name)
            return None

        page = pdf_doc[0]

        # DPI 기반 확대 행렬 계산
        # fitz 기본 해상도는 72 DPI이므로 zoom = dpi / 72
        zoom = dpi / 72.0
        mat = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=mat)

        # pixmap → NumPy 배열 (RGB)
        img_array = np.frombuffer(pix.samples, dtype=np.uint8).reshape(
            pix.height, pix.width, pix.n
        )

        pdf_doc.close()

        # RGB → BGR
        if img_array.shape[2] == 4:
            # RGBA → BGR (알파 채널 제거)
            img_array = img_array[:, :, :3]
        img_bgr = img_array[:, :, ::-1].copy()

        logger.info(
            "PDF 로드 (PyMuPDF): %s → %dx%d @ %d DPI",
            path.name,
            img_bgr.shape[1],
            img_bgr.shape[0],
            dpi,
        )
        return img_bgr

    except ImportError:
        logger.debug("PyMuPDF(fitz) 미설치, Pillow 폴백 시도")
    except Exception as exc:
        logger.warning("PyMuPDF PDF 로딩 실패: %s — %s", path.name, exc)

    # ── 방법 2: pdf2image (poppler 기반) ──
    try:
        from pdf2image import convert_from_path

        pages = convert_from_path(str(path), dpi=dpi, first_page=1, last_page=1)
        if pages:
            pil_img = pages[0].convert("RGB")
            arr = np.array(pil_img, dtype=np.uint8)
            img_bgr = arr[:, :, ::-1].copy()
            logger.info(
                "PDF 로드 (pdf2image): %s → %dx%d @ %d DPI",
                path.name,
                img_bgr.shape[1],
                img_bgr.shape[0],
                dpi,
            )
            return img_bgr
    except ImportError:
        logger.debug("pdf2image 미설치, 최종 Pillow 폴백 시도")
    except Exception as exc:
        logger.warning("pdf2image PDF 로딩 실패: %s — %s", path.name, exc)

    # ── 방법 3: Pillow 직접 (제한적) ──
    try:
        from PIL import Image as PILImage

        pil_img = PILImage.open(path)
        pil_img = pil_img.convert("RGB")
        arr = np.array(pil_img, dtype=np.uint8)
        img_bgr = arr[:, :, ::-1].copy()
        logger.info(
            "PDF 로드 (Pillow 제한): %s → %dx%d",
            path.name,
            img_bgr.shape[1],
            img_bgr.shape[0],
        )
        return img_bgr
    except Exception as exc:
        logger.error("모든 PDF 로딩 방법 실패: %s — %s", path.name, exc)
        return None


def _resize_long_edge(image: np.ndarray, target_size: int) -> np.ndarray:
    """장축 기준으로 이미지를 리사이즈합니다.

    종횡비를 유지하며 장축이 target_size가 되도록 축소/확대합니다.
    이미 target_size 이하이면 원본을 그대로 반환합니다.

    Args:
        image: 입력 이미지 배열.
        target_size: 장축 목표 크기 (px).

    Returns:
        리사이즈된 이미지 배열.
    """
    h, w = image.shape[:2]
    long_edge = max(h, w)

    if long_edge <= target_size:
        return image

    scale = target_size / long_edge
    new_w = int(w * scale)
    new_h = int(h * scale)

    if _HAS_CV2:
        return cv2.resize(image, (new_w, new_h), interpolation=cv2.INTER_AREA)

    # NumPy 기반 nearest-neighbor 리사이즈 (폴백)
    row_idx = (np.arange(new_h) * h / new_h).astype(int)
    col_idx = (np.arange(new_w) * w / new_w).astype(int)
    return image[np.ix_(row_idx, col_idx)]


def _generate_synthetic_numpy(
    width: int,
    height: int,
    wall_thickness: int,
    margin: int,
) -> np.ndarray:
    """OpenCV 없이 NumPy만으로 간단한 합성 도면을 생성합니다.

    사각형 외벽과 가로 내벽만 그려진 최소한의 도면을 반환합니다.
    """
    canvas = np.ones((height, width, 3), dtype=np.uint8) * 255

    x1, y1 = margin, margin
    x2, y2 = width - margin, height - margin
    mid_y = (y1 + y2) // 2
    wt = wall_thickness

    # 상단 벽
    canvas[y1 : y1 + wt, x1:x2] = 0
    # 하단 벽
    canvas[y2 - wt : y2, x1:x2] = 0
    # 좌측 벽
    canvas[y1:y2, x1 : x1 + wt] = 0
    # 우측 벽
    canvas[y1:y2, x2 - wt : x2] = 0
    # 가로 내벽
    canvas[mid_y - wt // 2 : mid_y + wt // 2, x1:x2] = 0

    # 문 개구부 (좌측 벽에 gap)
    door_y_start = mid_y + 30
    door_y_end = min(door_y_start + 50, y2 - wt)
    canvas[door_y_start:door_y_end, x1 : x1 + wt] = 255

    logger.info("합성 평면도 생성 (NumPy fallback): %dx%d px", width, height)
    return canvas
