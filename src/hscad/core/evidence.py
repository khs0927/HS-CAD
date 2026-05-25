"""Evidence, confidence and audit models.

All modules should emit evidence rather than mutating CAD drawings directly. This
keeps HS-CAD review-only by default and makes every result traceable.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any


JsonDict = dict[str, Any]


@dataclass(frozen=True)
class EvidenceSource:
    source_type: str
    source_id: str
    path: str | None = None
    module: str | None = None

    def to_record(self) -> JsonDict:
        return asdict(self)


@dataclass(frozen=True)
class ConfidenceScore:
    value: float
    reason: str = ""

    def __post_init__(self) -> None:
        if not 0.0 <= float(self.value) <= 1.0:
            raise ValueError("confidence value must be between 0.0 and 1.0")

    def to_record(self) -> JsonDict:
        return {"value": float(self.value), "reason": self.reason}


@dataclass(frozen=True)
class AuditTrail:
    actor: str
    action: str
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    details: JsonDict = field(default_factory=dict)

    def to_record(self) -> JsonDict:
        return asdict(self)


@dataclass(frozen=True)
class Evidence:
    evidence_id: str
    kind: str
    message: str
    source: EvidenceSource
    confidence: ConfidenceScore = field(default_factory=lambda: ConfidenceScore(1.0, "explicit"))
    entity_ids: list[str] = field(default_factory=list)
    data: JsonDict = field(default_factory=dict)
    audit: list[AuditTrail] = field(default_factory=list)

    def to_record(self) -> JsonDict:
        return {
            "evidence_id": self.evidence_id,
            "kind": self.kind,
            "message": self.message,
            "source": self.source.to_record(),
            "confidence": self.confidence.to_record(),
            "entity_ids": self.entity_ids,
            "data": self.data,
            "audit": [a.to_record() for a in self.audit],
        }


def make_evidence(
    evidence_id: str,
    kind: str,
    message: str,
    *,
    module: str,
    source_id: str = "pipeline",
    confidence: float = 1.0,
    reason: str = "generated",
    entity_ids: list[str] | None = None,
    data: JsonDict | None = None,
) -> Evidence:
    return Evidence(
        evidence_id=evidence_id,
        kind=kind,
        message=message,
        source=EvidenceSource(source_type="module", source_id=source_id, module=module),
        confidence=ConfidenceScore(confidence, reason),
        entity_ids=entity_ids or [],
        data=data or {},
        audit=[AuditTrail(actor=module, action="emit_evidence")],
    )
