"""Image/CAD coordinate conversion helpers.

이미지는 좌상단이 원점이고 y축이 아래로 증가한다.
CAD는 좌하단이 원점이고 y축이 위로 증가한다.
이 모듈은 이미지에서 검출된 픽셀 좌표를 CAD의 mm 좌표로 바꿀 때
한 곳에서만 공식을 관리하기 위해 분리했다.
"""

from __future__ import annotations

from typing import Iterable


PointLike = tuple[float, float] | list[float]
BBoxLike = tuple[float, float, float, float] | list[float]


def image_to_cad_point(point: PointLike, image_height: float, scale: float) -> tuple[float, float]:
    """Convert ``(x, y)`` from image pixels to CAD units.

    공식:
    cad_x = image_x * scale
    cad_y = (image_height - image_y) * scale

    여기서 scale은 pixel 하나가 몇 mm인지 나타내는 값이다.
    """

    x, y = float(point[0]), float(point[1])
    return x * scale, (float(image_height) - y) * scale


def cad_to_image_point(point: PointLike, image_height: float, scale: float) -> tuple[float, float]:
    """Convert ``(x, y)`` from CAD units back to image pixels."""

    if scale == 0:
        raise ValueError("scale must not be zero")
    x, y = float(point[0]), float(point[1])
    return x / scale, float(image_height) - (y / scale)


def image_bbox_to_cad_bbox(bbox: BBoxLike, image_height: float, scale: float) -> tuple[float, float, float, float]:
    """Convert image bbox ``[x1, y1, x2, y2]`` to CAD bbox.

    CAD 좌표로 변환하면 y축 방향이 뒤집히므로 네 꼭짓점을 변환한 뒤
    min/max를 다시 계산한다.
    """

    x1, y1, x2, y2 = [float(v) for v in bbox]
    corners = [
        image_to_cad_point((x1, y1), image_height, scale),
        image_to_cad_point((x2, y1), image_height, scale),
        image_to_cad_point((x2, y2), image_height, scale),
        image_to_cad_point((x1, y2), image_height, scale),
    ]
    xs = [p[0] for p in corners]
    ys = [p[1] for p in corners]
    return min(xs), min(ys), max(xs), max(ys)


def polyline_image_to_cad(points: Iterable[PointLike], image_height: float, scale: float) -> list[tuple[float, float]]:
    """Convert a polyline from image coordinates to CAD coordinates."""

    return [image_to_cad_point(point, image_height, scale) for point in points]

