from __future__ import annotations

from pathlib import Path

from neuro_seq_cad.line_extraction.raw_line_schema import RawLineResult


def extract_mlsd_lines(image_path: str | Path) -> tuple[RawLineResult, list[str]]:
    third_party = Path("third_party/mlsd")
    if not third_party.exists():
        return RawLineResult(lines=[]), ["model_adapter_missing: MLSD third_party/mlsd not found"]
    return RawLineResult(lines=[]), ["model_adapter_missing: MLSD adapter skeleton only"]

