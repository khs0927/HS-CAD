from dataclasses import dataclass

from neuro_seq_cad.geometry.wall_thickness_estimator import estimate_wall_thickness


@dataclass
class Candidate:
    spacing: float
    confidence: float


def test_double_line_candidate_has_priority():
    result = estimate_wall_thickness([Candidate(180, 0.9)], [120])
    assert result.thickness == 180
    assert result.source == "double_line_detector"


def test_polygon_thickness_is_second_priority():
    result = estimate_wall_thickness([], [100, 150, 200])
    assert result.thickness == 150
    assert result.source == "raster2seq_polygon"


def test_standard_fallback_candidates():
    result = estimate_wall_thickness([], [])
    assert result.thickness == 150
    assert {c["thickness"] for c in result.candidates} == {100, 150, 200}
    assert "wall_thickness_fallback" in result.warnings


def test_failure_without_fallback_warns():
    result = estimate_wall_thickness([], [], fallback_candidates=())
    assert result.thickness is None
    assert "wall_thickness_unresolved" in result.warnings

