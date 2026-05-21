from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class NeuroSeqCadSettings:
    default_scale: float = 1.0
    default_wall_thickness_mm: float = 150.0
    door_width_candidates_mm: tuple[int, ...] = (800, 850, 900, 1000)
