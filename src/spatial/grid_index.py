from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from src.spatial.geometry import BBox2D, Point2D


@dataclass(frozen=True)
class IndexedPolygon:
    index: int
    entity: dict[str, Any]
    polygon: list[Point2D]
    bbox: BBox2D


class UniformGridIndex:
    def __init__(self, polygons: list[IndexedPolygon], *, max_cells_per_polygon: int = 256):
        self.polygons = polygons
        self.max_cells_per_polygon = max_cells_per_polygon
        self.global_indices: set[int] = set()
        self.cells: dict[tuple[int, int], list[int]] = {}
        self.bounds = self._bounds(polygons)
        count = max(1, len(polygons))
        self.grid_size = max(8, min(256, int(math.sqrt(count) * 2)))
        if self.bounds is not None:
            self._build()

    def candidates(self, point: Point2D) -> list[IndexedPolygon]:
        if self.bounds is None or not self.polygons:
            return []
        cell = self._cell_for_point(point)
        indices = set(self.cells.get(cell, [])) | self.global_indices
        return [self.polygons[index] for index in indices]

    def stats(self) -> dict[str, Any]:
        cell_lengths = [len(value) for value in self.cells.values()]
        return {
            'polygon_count': len(self.polygons),
            'grid_size': self.grid_size,
            'cell_count': len(self.cells),
            'global_polygon_count': len(self.global_indices),
            'max_cell_candidates': max(cell_lengths) if cell_lengths else 0,
            'avg_cell_candidates': round(sum(cell_lengths) / len(cell_lengths), 3) if cell_lengths else 0,
        }

    def _build(self) -> None:
        for polygon in self.polygons:
            min_cell = self._cell_for_point(Point2D(polygon.bbox.min_x, polygon.bbox.min_y))
            max_cell = self._cell_for_point(Point2D(polygon.bbox.max_x, polygon.bbox.max_y))
            span = (max_cell[0] - min_cell[0] + 1) * (max_cell[1] - min_cell[1] + 1)
            if span > self.max_cells_per_polygon:
                self.global_indices.add(polygon.index)
                continue
            for cx in range(min_cell[0], max_cell[0] + 1):
                for cy in range(min_cell[1], max_cell[1] + 1):
                    self.cells.setdefault((cx, cy), []).append(polygon.index)

    def _cell_for_point(self, point: Point2D) -> tuple[int, int]:
        assert self.bounds is not None
        width = max(self.bounds.max_x - self.bounds.min_x, 1e-9)
        height = max(self.bounds.max_y - self.bounds.min_y, 1e-9)
        x = int((point.x - self.bounds.min_x) / width * self.grid_size)
        y = int((point.y - self.bounds.min_y) / height * self.grid_size)
        return (max(0, min(self.grid_size - 1, x)), max(0, min(self.grid_size - 1, y)))

    @staticmethod
    def _bounds(polygons: list[IndexedPolygon]) -> BBox2D | None:
        if not polygons:
            return None
        return BBox2D(
            min_x=min(item.bbox.min_x for item in polygons),
            min_y=min(item.bbox.min_y for item in polygons),
            max_x=max(item.bbox.max_x for item in polygons),
            max_y=max(item.bbox.max_y for item in polygons),
        )
