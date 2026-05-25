"""Coordinate conversion helpers."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ImageToCadTransform:
    image_width: float
    image_height: float
    scale: float = 1.0
    x_offset: float = 0.0
    y_offset: float = 0.0

    def point(self, image_x: float, image_y: float) -> tuple[float, float]:
        cad_x = image_x * self.scale + self.x_offset
        cad_y = (self.image_height - image_y) * self.scale + self.y_offset
        return cad_x, cad_y

    def polyline(self, points: list[tuple[float, float]]) -> list[tuple[float, float]]:
        return [self.point(x, y) for x, y in points]
