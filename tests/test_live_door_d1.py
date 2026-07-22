from __future__ import annotations

import math

import pytest

from xicad_mcp.headless_core_batch1 import Point3D
from xicad_mcp.headless_core_batch16 import (
    DoorLeafDivision,
    DoorRequest,
    DoorSwing,
    DoorVariant,
    SwingDisplay,
)
from xicad_mcp.live_door_d1 import build_live_d1_geometry


def _request(**updates: object) -> DoorRequest:
    values: dict[str, object] = {
        "document_id": "Drawing1.dwg",
        "variant": DoorVariant.D1,
        "hinge_point": Point3D(x=0, y=0, z=0),
        "opening_end_point": Point3D(x=1000, y=0, z=0),
        "wall_depth": 200,
        "offset": 0,
        "swing": DoorSwing.ONE_WAY,
        "leaf_division": DoorLeafDivision.EQUAL,
        "opening_angle_degrees": 90,
        "frame_width": 50,
        "leaf_thickness": 30,
        "threshold_depth": 0,
        "swing_display": SwingDisplay.ARC,
        "frame_layer": "A-DOOR",
        "swing_layer": "A-DOOR-SWING",
        "elevation_layer": "A-DOOR-ELEV",
        "group_output": False,
    }
    values.update(updates)
    return DoorRequest(**values)


def test_d1_builds_bounded_double_leaf_arc_geometry() -> None:
    geometry = build_live_d1_geometry(_request(), Point3D(x=0, y=100, z=0))

    assert geometry.clear_opening_width == 900
    assert geometry.leaf_lengths == (450, 450)
    assert geometry.opening_side_sign == 1
    assert len(geometry.frame_and_leaf_polylines) == 4
    assert len(geometry.swing_lines) == 0
    assert len(geometry.swing_arcs) == 2
    assert geometry.swing_arcs[0].center == Point3D(x=50, y=0, z=0)
    assert geometry.swing_arcs[1].center == Point3D(x=950, y=0, z=0)
    assert math.isclose(geometry.swing_arcs[0].sweep_angle_radians, math.pi / 2)
    assert math.isclose(geometry.swing_arcs[1].sweep_angle_radians, -math.pi / 2)


def test_d1_uses_explicit_two_to_one_leaf_ratio() -> None:
    geometry = build_live_d1_geometry(
        _request(leaf_division=DoorLeafDivision.TWO_TO_ONE),
        Point3D(x=0, y=100, z=0),
    )

    assert geometry.leaf_lengths == pytest.approx((600, 300))


def test_d1_line_display_outputs_chords_instead_of_arcs() -> None:
    geometry = build_live_d1_geometry(
        _request(swing_display=SwingDisplay.LINE),
        Point3D(x=0, y=-100, z=0),
    )

    assert geometry.opening_side_sign == -1
    assert len(geometry.swing_lines) == 2
    assert len(geometry.swing_arcs) == 0


@pytest.mark.parametrize(
    ("updates", "message"),
    [
        ({"variant": DoorVariant.D2}, "variant=d1"),
        ({"swing": DoorSwing.DOUBLE_ACTING}, "one_way"),
        ({"group_output": True}, "group_output"),
        ({"offset": 10}, "offset=0"),
        ({"threshold_depth": 10}, "threshold_depth=0"),
        ({"leaf_division": DoorLeafDivision.ONE_FIXED}, "fixed-leaf width"),
        ({"frame_width": 500}, "consume the entire opening"),
    ],
)
def test_d1_rejects_unrecovered_legacy_modes(updates: dict[str, object], message: str) -> None:
    with pytest.raises(ValueError, match=message):
        build_live_d1_geometry(_request(**updates), Point3D(x=0, y=100, z=0))


def test_d1_requires_a_non_collinear_side_point() -> None:
    with pytest.raises(ValueError, match="non-collinear"):
        build_live_d1_geometry(_request(), Point3D(x=500, y=0, z=0))


def test_d1_requires_one_elevation() -> None:
    with pytest.raises(ValueError, match="one elevation"):
        build_live_d1_geometry(_request(), Point3D(x=0, y=100, z=1))
