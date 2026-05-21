from __future__ import annotations

from pathlib import Path

from neuro_seq_cad.detection.symbol_schema import SymbolDetectionResult


def run_planparser(image_path: str | Path) -> tuple[SymbolDetectionResult, list[str]]:
    third_party = Path("third_party/planparser")
    if not third_party.exists():
        return SymbolDetectionResult(symbols=[]), [
            "model_adapter_missing: PlanParser third_party/planparser not found",
            "license_review_required: PlanParser/AGPL style dependencies must be reviewed before commercial use",
        ]
    return SymbolDetectionResult(symbols=[]), ["model_adapter_missing: PlanParser weights not configured"]

