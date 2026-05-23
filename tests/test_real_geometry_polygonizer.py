from src.spatial.real_geometry_polygonizer import polygonize_full

def test_polygonize_full_rectangle():
    entities = [
        {'entity_type': 'LINE', 'start': [0, 0], 'end': [10, 0]},
        {'entity_type': 'LINE', 'start': [10, 0], 'end': [10, 10]},
        {'entity_type': 'LINE', 'start': [10, 10], 'end': [0, 10]},
        {'entity_type': 'LINE', 'start': [0, 10], 'end': [0, 0]}
    ]
    polygons = polygonize_full(entities)
    assert len(polygons) == 1
    assert polygons[0].area == 100.0

def test_polygonize_full_circle():
    entities = [
        {'entity_type': 'CIRCLE', 'center': [0, 0], 'radius': 10}
    ]
    polygons = polygonize_full(entities)
    assert len(polygons) == 1
    # Area should be close to pi * r^2 (314.159)
    assert 310.0 < polygons[0].area < 315.0
