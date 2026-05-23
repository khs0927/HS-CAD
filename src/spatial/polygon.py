from __future__ import annotations

from src.spatial.geometry import Point2D


def point_in_polygon(point: Point2D, polygon: list[Point2D]) -> bool:
    if len(polygon) < 3:
        return False
    if point_on_polygon_boundary(point, polygon):
        return True
    inside = False
    previous = len(polygon) - 1
    for index, current_point in enumerate(polygon):
        previous_point = polygon[previous]
        y_crosses = (current_point.y > point.y) != (previous_point.y > point.y)
        if y_crosses:
            x_at_y = (previous_point.x - current_point.x) * (point.y - current_point.y) / ((previous_point.y - current_point.y) or 1e-12) + current_point.x
            if point.x < x_at_y:
                inside = not inside
        previous = index
    return inside


def point_on_polygon_boundary(point: Point2D, polygon: list[Point2D], eps: float = 1e-9) -> bool:
    previous = len(polygon) - 1
    for index, current_point in enumerate(polygon):
        previous_point = polygon[previous]
        if point_on_segment(point, previous_point, current_point, eps=eps):
            return True
        previous = index
    return False


def point_on_segment(point: Point2D, start: Point2D, end: Point2D, eps: float = 1e-9) -> bool:
    cross = (point.y - start.y) * (end.x - start.x) - (point.x - start.x) * (end.y - start.y)
    if abs(cross) > eps:
        return False
    dot = (point.x - start.x) * (end.x - start.x) + (point.y - start.y) * (end.y - start.y)
    if dot < -eps:
        return False
    length_sq = (end.x - start.x) ** 2 + (end.y - start.y) ** 2
    return dot <= length_sq + eps
