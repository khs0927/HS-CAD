"""Evidence fusion layer for next-stage HS-CAD."""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from statistics import mean
from typing import Any, Iterable

from hscad.core.evidence import ConfidenceScore, Evidence, EvidenceKind, EvidenceSource, evidence_from_mapping
from hscad.core.jsonio import write_json


@dataclass
class FusionGroup:
    key: str
    evidence_ids: list[str]
    sources: list[str]
    kinds: list[str]
    confidence: float
    payload_summary: dict[str, Any] = field(default_factory=dict)


@dataclass
class ConflictCandidate:
    conflict_id: str
    key: str
    reason: str
    evidence_ids: list[str]
    severity: str = "review"


@dataclass
class EvidenceFusionResult:
    groups: list[FusionGroup]
    conflicts: list[ConflictCandidate]
    evidence: list[Evidence]

    def to_record(self) -> dict[str, Any]:
        return {
            "groups": [group.__dict__ for group in self.groups],
            "conflicts": [conflict.__dict__ for conflict in self.conflicts],
            "evidence": [item.to_record() for item in self.evidence],
        }

    def write_outputs(self, out_dir: str | Path) -> dict[str, str]:
        out = Path(out_dir)
        paths = {
            "FUSION_MATRIX": write_json(out / "FUSION_MATRIX.json", self.to_record()),
            "CROSS_VALIDATION": write_json(out / "CROSS_VALIDATION.json", {"conflicts": [c.__dict__ for c in self.conflicts]}),
        }
        return {key: str(path) for key, path in paths.items()}


class EvidenceFusionEngine:
    def fuse(self, evidence_items: Iterable[Evidence | dict[str, Any]]) -> EvidenceFusionResult:
        evidence = [item if isinstance(item, Evidence) else evidence_from_mapping(item) for item in evidence_items]
        buckets: dict[str, list[Evidence]] = defaultdict(list)
        for item in evidence:
            key = item.entity_id or item.payload.get("entity_id") or item.payload.get("layer") or item.kind_value
            buckets[str(key)].append(item)

        groups: list[FusionGroup] = []
        conflicts: list[ConflictCandidate] = []
        fusion_evidence: list[Evidence] = []
        for key, items in sorted(buckets.items(), key=lambda kv: kv[0]):
            confidence = mean(item.confidence.value for item in items) if items else 0.0
            sources = sorted({item.source_value for item in items})
            kinds = sorted({item.kind_value for item in items})
            groups.append(
                FusionGroup(
                    key=key,
                    evidence_ids=[item.evidence_id for item in items],
                    sources=sources,
                    kinds=kinds,
                    confidence=round(confidence, 4),
                    payload_summary={"count": len(items)},
                )
            )
            if len({item.kind_value for item in items}) > 1 and any(item.kind_value == EvidenceKind.ERROR.value for item in items):
                conflicts.append(
                    ConflictCandidate(
                        conflict_id=f"conflict-{len(conflicts)+1:04d}",
                        key=key,
                        reason="error evidence exists with other evidence kinds for the same key",
                        evidence_ids=[item.evidence_id for item in items],
                        severity="warning",
                    )
                )
            fusion_evidence.append(
                Evidence(
                    source=EvidenceSource.SYSTEM,
                    kind=EvidenceKind.PLAN,
                    entity_id=f"fusion:{key}",
                    payload={"key": key, "sources": sources, "kinds": kinds, "input_evidence_count": len(items)},
                    confidence=ConfidenceScore(confidence, reason="mean of grouped evidence", method="mean_group_confidence"),
                    tags=["fusion"],
                )
            )
        return EvidenceFusionResult(groups=groups, conflicts=conflicts, evidence=fusion_evidence)
