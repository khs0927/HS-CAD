"""
coordinate_system.py — 이미지 ↔ CAD 좌표 변환 (Image ↔ CAD coordinate transform)

==========================================================================
좌표계 정의:
--------------------------------------------------------------------------
  [이미지 좌표계]                    [CAD 좌표계]
  원점: 왼쪽 상단                    원점: 왼쪽 하단
  X축: 오른쪽 →                     X축: 오른쪽 →
  Y축: 아래쪽 ↓                     Y축: 위쪽 ↑
  단위: 픽셀 (px)                    단위: 밀리미터 (mm) 또는 축적에 따라

변환 공식 (Image → CAD):
  cad_x = img_x × scale_factor
  cad_y = (image_height − img_y) × scale_factor

  설명:
    - X축은 방향이 동일하므로 스케일만 적용합니다.
    - Y축은 방향이 반대이므로, 이미지 높이에서 빼서
      하단 원점 기준으로 변환한 뒤 스케일을 적용합니다.

역변환 공식 (CAD → Image):
  img_x = cad_x / scale_factor
  img_y = image_height − (cad_y / scale_factor)

  설명:
    - CAD 좌표를 스케일로 나눠 픽셀 단위로 복원합니다.
    - Y축은 다시 이미지 높이에서 빼서 상단 원점 기준으로 되돌립니다.
==========================================================================
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import List, Sequence, Tuple, Union

logger = logging.getLogger(__name__)

# 타입 앨리어스
Point2D = Tuple[float, float]
BBox = Tuple[float, float, float, float]  # (x1, y1, x2, y2)


@dataclass
class CADBoundingBox:
    """CAD 좌표계 바운딩 박스.

    Attributes:
        min_x: 좌측 X 좌표 (mm)
        min_y: 하단 Y 좌표 (mm)
        max_x: 우측 X 좌표 (mm)
        max_y: 상단 Y 좌표 (mm)
    """

    min_x: float
    min_y: float
    max_x: float
    max_y: float

    @property
    def width(self) -> float:
        """박스 너비 (mm)."""
        return self.max_x - self.min_x

    @property
    def height(self) -> float:
        """박스 높이 (mm)."""
        return self.max_y - self.min_y

    @property
    def center(self) -> Point2D:
        """박스 중심점 좌표 (mm)."""
        return (
            (self.min_x + self.max_x) / 2.0,
            (self.min_y + self.max_y) / 2.0,
        )

    def as_tuple(self) -> BBox:
        """(min_x, min_y, max_x, max_y) 튜플로 반환."""
        return (self.min_x, self.min_y, self.max_x, self.max_y)


class ImageToCADTransformer:
    """이미지 좌표 ↔ CAD 좌표 양방향 변환기.

    이미지 좌표계(왼쪽 상단 원점, Y↓)와 CAD 좌표계(왼쪽 하단 원점, Y↑)
    사이의 좌표 변환을 수행합니다. 스케일 팩터를 통해 픽셀 → mm 단위
    변환도 동시에 처리합니다.

    Args:
        image_height: 원본 이미지의 세로 크기 (px).
        scale_factor: 1 px당 CAD 단위 (mm) 변환 계수.
                      예) scale_factor=10.0 → 1px = 10mm.

    Example:
        >>> tf = ImageToCADTransformer(image_height=1000, scale_factor=10.0)
        >>> tf.to_cad(50, 200)
        (500.0, 8000.0)
        >>> tf.to_image(500.0, 8000.0)
        (50.0, 200.0)
    """

    __slots__ = ("_image_height", "_scale_factor")

    def __init__(self, image_height: int, scale_factor: float = 1.0) -> None:
        if image_height <= 0:
            raise ValueError(
                f"image_height는 양수여야 합니다. 입력값: {image_height}"
            )
        if scale_factor <= 0:
            raise ValueError(
                f"scale_factor는 양수여야 합니다. 입력값: {scale_factor}"
            )

        self._image_height: int = image_height
        self._scale_factor: float = scale_factor

    # ------------------------------------------------------------------
    # 읽기 전용 속성 (Read-only properties)
    # ------------------------------------------------------------------
    @property
    def image_height(self) -> int:
        """원본 이미지 세로 크기 (px)."""
        return self._image_height

    @property
    def scale_factor(self) -> float:
        """px → CAD 단위(mm) 스케일 팩터."""
        return self._scale_factor

    # ------------------------------------------------------------------
    # 단일 좌표 변환 (Single point transforms)
    # ------------------------------------------------------------------
    def to_cad(self, x: float, y: float) -> Point2D:
        """이미지 좌표 (px) → CAD 좌표 (mm) 변환.

        변환 수식:
          cad_x = x × scale
          cad_y = (image_height − y) × scale

        이미지의 Y축은 위에서 아래로 증가하지만,
        CAD의 Y축은 아래에서 위로 증가하므로
        image_height에서 y를 빼서 방향을 반전시킵니다.

        Args:
            x: 이미지 X 좌표 (px, 왼쪽 기준).
            y: 이미지 Y 좌표 (px, 상단 기준).

        Returns:
            (cad_x, cad_y) — CAD 좌표 (mm).
        """
        # X축: 방향 동일 → 스케일만 적용
        cad_x = x * self._scale_factor

        # Y축: 방향 반전 → (이미지높이 − y)로 하단 기준 변환 후 스케일 적용
        cad_y = (self._image_height - y) * self._scale_factor

        return (cad_x, cad_y)

    def transform(self, x: float, y: float) -> Point2D:
        """CoordinateTransformer 프로토콜 호환을 위한 to_cad 에일리어스."""
        return self.to_cad(x, y)

    def to_image(self, cad_x: float, cad_y: float) -> Point2D:
        """CAD 좌표 (mm) → 이미지 좌표 (px) 역변환.

        역변환 수식:
          img_x = cad_x / scale
          img_y = image_height − (cad_y / scale)

        CAD의 Y값을 스케일로 나눠 픽셀 단위로 되돌린 후,
        image_height에서 빼서 상단 원점 기준으로 복원합니다.

        Args:
            cad_x: CAD X 좌표 (mm).
            cad_y: CAD Y 좌표 (mm).

        Returns:
            (img_x, img_y) — 이미지 좌표 (px).
        """
        # X축: 스케일 역산
        img_x = cad_x / self._scale_factor

        # Y축: 스케일 역산 후 이미지 높이에서 빼서 상단 원점 기준으로 복원
        img_y = self._image_height - (cad_y / self._scale_factor)

        return (img_x, img_y)

    # ------------------------------------------------------------------
    # 배치 좌표 변환 (Batch point transforms)
    # ------------------------------------------------------------------
    def transform_points(
        self,
        points: Sequence[Point2D],
        *,
        to_cad: bool = True,
    ) -> List[Point2D]:
        """여러 점을 한꺼번에 변환합니다.

        Args:
            points: (x, y) 좌표 리스트.
            to_cad: True → 이미지→CAD, False → CAD→이미지.

        Returns:
            변환된 (x, y) 좌표 리스트 (입력과 동일한 순서).
        """
        fn = self.to_cad if to_cad else self.to_image
        return [fn(x, y) for x, y in points]

    def transform_points_numpy(
        self,
        points: "numpy.ndarray",
        *,
        to_cad: bool = True,
    ) -> "numpy.ndarray":
        """NumPy 배열 (N, 2) 좌표를 벡터 연산으로 일괄 변환합니다.

        벡터화 수식 (Image → CAD):
          result[:, 0] = points[:, 0] × scale
          result[:, 1] = (image_height − points[:, 1]) × scale

        대량의 점을 처리할 때 for-loop 대비 10~50배 빠릅니다.

        Args:
            points: (N, 2) shape의 NumPy 배열.
            to_cad: True → 이미지→CAD, False → CAD→이미지.

        Returns:
            변환된 (N, 2) NumPy 배열.

        Raises:
            ImportError: numpy가 없을 때.
            ValueError: 배열 shape이 (N, 2)가 아닐 때.
        """
        try:
            import numpy as np
        except ImportError as exc:
            raise ImportError(
                "numpy 패키지가 필요합니다. 설치: pip install numpy"
            ) from exc

        points = np.asarray(points, dtype=np.float64)
        if points.ndim != 2 or points.shape[1] != 2:
            raise ValueError(
                f"points shape은 (N, 2)여야 합니다. 입력: {points.shape}"
            )

        result = np.empty_like(points)

        if to_cad:
            # 이미지 → CAD 벡터 변환
            result[:, 0] = points[:, 0] * self._scale_factor
            result[:, 1] = (self._image_height - points[:, 1]) * self._scale_factor
        else:
            # CAD → 이미지 벡터 역변환
            result[:, 0] = points[:, 0] / self._scale_factor
            result[:, 1] = self._image_height - (points[:, 1] / self._scale_factor)

        return result

    # ------------------------------------------------------------------
    # 바운딩 박스 변환 (Bounding box transforms)
    # ------------------------------------------------------------------
    def transform_bbox(
        self,
        bbox: Union[BBox, Sequence[float]],
    ) -> CADBoundingBox:
        """이미지 바운딩 박스 (x1, y1, x2, y2) → CAD 바운딩 박스로 변환.

        이미지 bbox에서 (x1, y1)은 왼쪽 상단, (x2, y2)는 오른쪽 하단입니다.
        CAD에서는 Y축이 반전되므로:
          - y1(상단)이 CAD에서는 max_y(위쪽)가 됩니다.
          - y2(하단)이 CAD에서는 min_y(아래쪽)가 됩니다.

        변환 과정:
          cad_x1 = img_x1 × scale    (왼쪽 X는 그대로 min_x)
          cad_x2 = img_x2 × scale    (오른쪽 X는 그대로 max_x)
          cad_y_top = (H − img_y1) × scale  → max_y
          cad_y_bot = (H − img_y2) × scale  → min_y

        Args:
            bbox: 이미지 좌표계 bbox (x1, y1, x2, y2), px 단위.

        Returns:
            CADBoundingBox — CAD 좌표계 바운딩 박스 (mm 단위).
        """
        if len(bbox) != 4:
            raise ValueError(
                f"bbox는 4개 요소 (x1, y1, x2, y2) 필요. 입력: {len(bbox)}개"
            )

        img_x1, img_y1, img_x2, img_y2 = bbox

        # 왼쪽 상단 → CAD (왼쪽 상단은 CAD에서 Y가 큼)
        cad_x1, cad_y1 = self.to_cad(img_x1, img_y1)

        # 오른쪽 하단 → CAD (오른쪽 하단은 CAD에서 Y가 작음)
        cad_x2, cad_y2 = self.to_cad(img_x2, img_y2)

        # CAD bbox는 항상 min < max 순서로 정렬
        return CADBoundingBox(
            min_x=min(cad_x1, cad_x2),
            min_y=min(cad_y1, cad_y2),
            max_x=max(cad_x1, cad_x2),
            max_y=max(cad_y1, cad_y2),
        )

    def transform_bbox_inverse(
        self,
        cad_bbox: CADBoundingBox,
    ) -> BBox:
        """CAD 바운딩 박스 → 이미지 바운딩 박스 (x1, y1, x2, y2) 역변환.

        CAD bbox의 (min_x, max_y)가 이미지 왼쪽 상단,
                   (max_x, min_y)가 이미지 오른쪽 하단이 됩니다.

        Args:
            cad_bbox: CAD 좌표계 바운딩 박스.

        Returns:
            (img_x1, img_y1, img_x2, img_y2) — 이미지 좌표계 bbox (px).
        """
        # CAD 왼쪽 상단 (min_x, max_y) → 이미지 왼쪽 상단
        img_x1, img_y1 = self.to_image(cad_bbox.min_x, cad_bbox.max_y)

        # CAD 오른쪽 하단 (max_x, min_y) → 이미지 오른쪽 하단
        img_x2, img_y2 = self.to_image(cad_bbox.max_x, cad_bbox.min_y)

        return (img_x1, img_y1, img_x2, img_y2)

    # ------------------------------------------------------------------
    # 선분 변환 (Line segment transform)
    # ------------------------------------------------------------------
    def transform_line(
        self,
        x1: float,
        y1: float,
        x2: float,
        y2: float,
    ) -> Tuple[Point2D, Point2D]:
        """이미지 선분 (x1,y1)→(x2,y2)를 CAD 선분으로 변환.

        MLSD 등 라인 검출기의 출력 [x1, y1, x2, y2] 형식에 대응합니다.

        Args:
            x1, y1: 시작점 이미지 좌표 (px).
            x2, y2: 끝점 이미지 좌표 (px).

        Returns:
            ((cad_x1, cad_y1), (cad_x2, cad_y2)) 튜플.
        """
        return self.to_cad(x1, y1), self.to_cad(x2, y2)

    # ------------------------------------------------------------------
    # 유틸리티 (Utilities)
    # ------------------------------------------------------------------
    def __repr__(self) -> str:
        return (
            f"ImageToCADTransformer("
            f"image_height={self._image_height}, "
            f"scale_factor={self._scale_factor})"
        )

    def describe(self) -> str:
        """변환기 설정을 사람이 읽기 쉬운 문자열로 반환합니다."""
        return (
            f"좌표 변환기 설정:\n"
            f"  이미지 높이: {self._image_height} px\n"
            f"  스케일 팩터: {self._scale_factor} (1 px = {self._scale_factor} mm)\n"
            f"  이미지 원점 (0, 0) → CAD ({0.0}, {self._image_height * self._scale_factor})\n"
            f"  이미지 하단 (0, {self._image_height}) → CAD (0.0, 0.0)"
        )
