from __future__ import annotations

from neuro_seq_cad.line_extraction.raw_line_schema import RawLine


def merge_collinear_lines(lines: list[RawLine], opening_ranges: list[tuple[float, float]] | None = None) -> list[RawLine]:
    # Conservative placeholder: preserve source evidence until opening-aware merge is stronger.
    return lines

