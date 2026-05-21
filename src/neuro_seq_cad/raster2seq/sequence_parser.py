from __future__ import annotations

from neuro_seq_cad.raster2seq.polygon_schema import Raster2SeqResult


def parse_sequence_payload(payload: dict | None) -> Raster2SeqResult:
    if not payload:
        return Raster2SeqResult(polygons=[])
    return Raster2SeqResult.model_validate(payload)

