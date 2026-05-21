from __future__ import annotations

from pathlib import Path

from neuro_seq_cad.raster2seq.polygon_schema import Raster2SeqResult


def run_raster2seq(image_path: str | Path) -> tuple[Raster2SeqResult, list[str]]:
    third_party = Path("third_party/Raster2Seq")
    if not third_party.exists():
        return Raster2SeqResult(polygons=[]), ["model_adapter_missing: Raster2Seq third_party/Raster2Seq not found"]
    return Raster2SeqResult(polygons=[]), ["model_adapter_missing: Raster2Seq checkpoint not configured"]

