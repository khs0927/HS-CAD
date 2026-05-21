from __future__ import annotations

from dataclasses import dataclass

from neuro_seq_cad.line_extraction.raw_line_schema import RawLine


@dataclass(frozen=True)
class DoubleLineCandidate:
    line_a: RawLine
    line_b: RawLine
    spacing: float
    confidence: float


def detect_double_lines(lines: list[RawLine], scale: float | None = None) -> list[DoubleLineCandidate]:
    candidates: list[DoubleLineCandidate] = []
    for i, a in enumerate(lines):
        for b in lines[i + 1:]:
            same_orientation = abs((a.angle - b.angle + 180) % 180) < 5 or abs((a.angle - b.angle) % 180) < 5
            if not same_orientation:
                continue
            if abs(a.angle) < 10 or abs(abs(a.angle) - 180) < 10:
                spacing_px = abs(a.p1[1] - b.p1[1])
            elif abs(abs(a.angle) - 90) < 10:
                spacing_px = abs(a.p1[0] - b.p1[0])
            else:
                continue
            spacing_mm = spacing_px * scale if scale else spacing_px
            valid = 80 <= spacing_mm <= 300 if scale else 8 <= spacing_px <= 40
            if valid:
                candidates.append(DoubleLineCandidate(a, b, spacing_mm, 0.78))
    return candidates

