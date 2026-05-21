from __future__ import annotations

from neuro_seq_cad.geometry.scale_calibration import normalize_dimension_text


def parse_dimension_texts(texts: list[str]) -> list[float]:
    return [v for text in texts if (v := normalize_dimension_text(text)) is not None]

