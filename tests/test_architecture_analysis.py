from src.modifiers.architectural_modifier import (
    check_closed_polylines,
    create_grid,
    generate_architecture_summary,
    place_beams_2d,
)


def test_create_grid_with_origin():
    actions = create_grid(width=12000, depth=6000, grid_x=6000, grid_y=3000, origin=(100, 200, 0))
    assert actions[0]['start'] == [100.0, 200.0, 0.0]
    assert actions[-1]['end'][0] == 12100.0


def test_place_beams_2d():
    actions = place_beams_2d(width=6000, depth=6000, grid_x=6000, grid_y=6000)
    assert len(actions) == 4
    assert all(a['action'] == 'create_line' for a in actions)


def test_architecture_summary_counts():
    objects = [
        {'entity_type': 'LINE', 'layer': 'A-WALL'},
        {'entity_type': 'INSERT', 'layer': 'A-DOOR', 'name': 'D900'},
        {'entity_type': 'POLYLINE', 'layer': 'A-AREA', 'closed': True},
        {'entity_type': 'TEXT', 'layer': 'A-ROOM', 'text': '사무실 12㎡'},
    ]
    summary = generate_architecture_summary(objects)
    assert summary['object_count'] == 4
    assert summary['block_counts']['D900'] == 1
    assert summary['polyline_quality']['closed_count'] == 1
    assert len(summary['room_texts']) == 1
