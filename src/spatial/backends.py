from __future__ import annotations

import importlib.util
from dataclasses import asdict, dataclass
from typing import Any, Protocol

from src.spatial.geometry import BBox2D, Point2D, bbox_from_points
from src.spatial.polygon import point_in_polygon


@dataclass
class SpatialBackendStatus:
    backend_id: str
    available: bool
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class SpatialBackend(Protocol):
    backend_id: str

    def is_available(self) -> SpatialBackendStatus: ...
    def polygon_area(self, points: list[Point2D]) -> float: ...
    def contains_point(self, polygon: list[Point2D], point: Point2D) -> bool: ...
    def bounds(self, points: list[Point2D]) -> BBox2D | None: ...


class PurePythonSpatialBackend:
    backend_id = 'pure_python'

    def is_available(self) -> SpatialBackendStatus:
        return SpatialBackendStatus(self.backend_id, True, 'built-in fallback')

    def polygon_area(self, points: list[Point2D]) -> float:
        if len(points) < 3:
            return 0.0
        area = 0.0
        previous = points[-1]
        for current in points:
            area += previous.x * current.y - current.x * previous.y
            previous = current
        return area / 2.0

    def contains_point(self, polygon: list[Point2D], point: Point2D) -> bool:
        return point_in_polygon(point, polygon)

    def bounds(self, points: list[Point2D]) -> BBox2D | None:
        return bbox_from_points(points)


class ShapelySpatialBackend:
    backend_id = 'shapely'

    def is_available(self) -> SpatialBackendStatus:
        if importlib.util.find_spec('shapely') is None:
            return SpatialBackendStatus(self.backend_id, False, 'shapely not installed')
        return SpatialBackendStatus(self.backend_id, True, 'shapely installed')

    def polygon_area(self, points: list[Point2D]) -> float:
        polygon = self._polygon(points)
        return float(polygon.area) if polygon is not None else 0.0

    def contains_point(self, polygon: list[Point2D], point: Point2D) -> bool:
        shape = self._polygon(polygon)
        if shape is None:
            return False
        from shapely.geometry import Point

        pt = Point(point.x, point.y)
        return bool(shape.contains(pt) or shape.touches(pt))

    def bounds(self, points: list[Point2D]) -> BBox2D | None:
        polygon = self._polygon(points)
        if polygon is None:
            return bbox_from_points(points)
        min_x, min_y, max_x, max_y = polygon.bounds
        return BBox2D(float(min_x), float(min_y), float(max_x), float(max_y))

    @staticmethod
    def _polygon(points: list[Point2D]):
        if len(points) < 3:
            return None
        from shapely.geometry import Polygon

        polygon = Polygon([(point.x, point.y) for point in points])
        if polygon.is_empty:
            return None
        if not polygon.is_valid:
            polygon = polygon.buffer(0)
        return polygon if not polygon.is_empty else None


def get_spatial_backend(name: str = 'auto') -> SpatialBackend:
    normalized = name.lower().strip()
    if normalized == 'pure':
        return PurePythonSpatialBackend()
    if normalized == 'shapely':
        backend = ShapelySpatialBackend()
        if backend.is_available().available:
            return backend
        return PurePythonSpatialBackend()
    if normalized == 'auto':
        backend = ShapelySpatialBackend()
        if backend.is_available().available:
            return backend
        return PurePythonSpatialBackend()
    return PurePythonSpatialBackend()


def spatial_backend_summary() -> dict[str, Any]:
    candidates = [PurePythonSpatialBackend(), ShapelySpatialBackend()]
    return {
        'default_backend': get_spatial_backend('auto').backend_id,
        'backends': [candidate.is_available().to_dict() for candidate in candidates],
    }
