"""Evidence fusion and cross-validation."""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from statistics import mean
from typing import Any, Iterable

from hscad.core.evidence import Evidence
from hscad.core.jsonio import write_json


@dataclass(frozen=True)
class FusionResult:
    evidence_count: int
    by_kind: dict[str, int]
    average_confidence_by_kind: dict[str, float]
    conflicts: list[dict[str, Any]]
    recommendations: list[dict[str, Any]]

    def to_record(self) -> dict[str, Any]:
        return self.__dict__.copy()


class EvidenceFusionEngine:
    def fuse(self, evidence: Iterable[Evidence]) -> FusionResult:
        ev = list(evidence)
        grouped: dict[str, list[Evidence]] = defaultdict(list)
        for item in ev:
            grouped[item.kind].append(item)
        by_kind = {kind: len(items) for kind, items in grouped.items()}
        avg = {kind: round(mean(i.confidence.value for i in items), 4) for kind, items in grouped.items()}
        conflicts = self._find_conflicts(ev)
        recs = self._recommend(ev, conflicts)
        return FusionResult(len(ev), by_kind, avg, conflicts, recs)

    def write_outputs(self, out_dir: str | Path, result: FusionResult) -> dict[str, str]:
        out = Path(out_dir)
        matrix = write_json(out / "FUSION_MATRIX.json", result.to_record())
        cross = write_json(out / "CROSS_VALIDATION.json", {"conflicts": result.conflicts, "recommendations": result.recommendations})
        return {"fusion_matrix": str(matrix), "cross_validation": str(cross)}

    def _find_conflicts(self, evidence: list[Evidence]) -> list[dict[str, Any]]:
        conflicts: list[dict[str, Any]] = []
        for item in evidence:
            if item.confidence.value < 0.4:
                conflicts.append({"type": "low_confidence", "evidence_id": item.evidence_id, "kind": item.kind, "message": item.message, "confidence": item.confidence.value})
            if item.kind in {"unsupported_input", "conversion_required", "adapter_boundary"}:
                conflicts.append({"type": "pipeline_gap", "evidence_id": item.evidence_id, "kind": item.kind, "message": item.message})
        return conflicts

    def _recommend(self, evidence: list[Evidence], conflicts: list[dict[str, Any]]) -> list[dict[str, Any]]:
        recs: list[dict[str, Any]] = []
        if any(c["type"] == "pipeline_gap" for c in conflicts):
            recs.append({"priority": "P1", "action": "enable_or_configure_adapter", "details": "Enable ODAFC/PDF/image adapters before live CAD changes"})
        if any(c["type"] == "low_confidence" for c in conflicts):
            recs.append({"priority": "P1", "action": "manual_review_required", "details": "Review low-confidence evidence in QA overlay"})
        if not recs:
            recs.append({"priority": "P2", "action": "connect_to_existing_pipeline", "details": "Wire evidence outputs into existing analyzer/report pipeline"})
        return recs
