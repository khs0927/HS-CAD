from __future__ import annotations

from src.spatial.backends import PurePythonSpatialBackend, get_spatial_backend, spatial_backend_summary
from src.spatial.geometry import Point2D


def test_pure_python_spatial_backend_area_and_contains():
    backend = PurePythonSpatialBackend()
    polygon = [Point2D(0, 0), Point2D(10, 0), Point2D(10, 10), Point2D(0, 10)]
    assert backend.is_available().available is True
    assert backend.polygon_area(polygon) == 100
    assert backend.contains_point(polygon, Point2D(5, 5)) is True
    assert backend.contains_point(polygon, Point2D(20, 5)) is False


def test_get_spatial_backend_never_fails_for_auto_or_shapely():
    assert get_spatial_backend('auto').backend_id in {'pure_python', 'shapely'}
    assert get_spatial_backend('pure').backend_id == 'pure_python'
    assert get_spatial_backend('shapely').backend_id in {'pure_python', 'shapely'}


def test_spatial_backend_summary_is_json_ready():
    summary = spatial_backend_summary()
    assert summary['default_backend'] in {'pure_python', 'shapely'}
    assert any(item['backend_id'] == 'pure_python' for item in summary['backends'])
    assert any(item['backend_id'] == 'shapely' for item in summary['backends'])
