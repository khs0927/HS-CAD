from __future__ import annotations

from pathlib import Path

from neuro_seq_cad.detection.symbol_schema import SymbolDetectionResult


def run_yolo(image_path: str | Path) -> tuple[SymbolDetectionResult, list[str]]:
    try:
        import ultralytics  # type: ignore  # noqa: F401
    except Exception:
        return SymbolDetectionResult(symbols=[]), ["optional_dependency_missing: ultralytics is not installed"]
    return SymbolDetectionResult(symbols=[]), ["model_adapter_missing: YOLO weights not configured"]

