from shapely.geometry import Point, box
from src.spatial.spatial_index_service import SpatialIndexService

def test_spatial_index_intersects():
    boxes = [
        box(0, 0, 10, 10),
        box(20, 20, 30, 30),
        box(5, 5, 15, 15)
    ]
    service = SpatialIndexService(boxes)
    
    # Query with a point at (6, 6) -> intersects box 0 and box 2
    pt = Point(6, 6)
    results = service.query_intersects(pt)
    assert len(results) == 2
    assert boxes[0] in results
    assert boxes[2] in results

def test_spatial_index_nearest():
    boxes = [
        box(0, 0, 10, 10),
        box(100, 100, 110, 110)
    ]
    service = SpatialIndexService(boxes)
    
    # Query nearest to point (90, 90) -> should be Box(100, 100, 110, 110)
    pt = Point(90, 90)
    nearest = service.query_nearest(pt)
    assert nearest == boxes[1]
