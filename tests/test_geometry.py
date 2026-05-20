from src.utils.geometry import chunk_points, bbox_from_points

def test_chunk_points():
    assert chunk_points([0,0,1,1], 2) == [[0,0],[1,1]]

def test_bbox():
    b = bbox_from_points([[0,0],[10,5]])
    assert b['width'] == 10
    assert b['height'] == 5
