"""Evidence and confidence models for HS-CAD.

The goal is to make every analyzer and fileizer return explainable, auditable
objects rather than opaque dictionaries.  This is deliberately lightweight and
uses only the Python standard library.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Mapping
from uuid import uuid4


class EvidenceSource(str, Enum):
    DXF = "dxf"
    DWG = "dwg"
    PDF = "pdf"
    IMAGE = "image"
    OCR = "ocr"
    VISION = "vision"
    SHAPELY = "shapely"
    DOMAIN_RULE = "domain_rule"
    USER = "user"
    SYSTEM = "system"


class EvidenceKind(str, Enum):
    ENTITY = "entity"
    TEXT = "text"
    LAYER = "layer"
    GEOMETRY = "geometry"
    AREA = "area"
    WARNING = "warning"
    ERROR = "error"
    PLAN = "plan"
    RULE_RESULT = "rule_result"


@dataclass(frozen=True)
class ConfidenceScore:
    value: float
    reason: str = ""
    method: str = "manual_or_rule_based"

    def __post_init__(self) -> None:
        if not 0.0 <= self.value <= 1.0:
            raise ValueError(f"confidence must be between 0 and 1, got {self.value}")

    @classmethod
    def high(cls, reason: str = "") -> "ConfidenceScore":
        return cls(0.9, reason=reason, method="preset")

    @classmethod
    def medium(cls, reason: str = "") -> "ConfidenceScore":
        return cls(0.6, reason=reason, method="preset")

    @classmethod
    def low(cls, reason: str = "") -> "ConfidenceScore":
        return cls(0.3, reason=reason, method="preset")


@dataclass
class AuditTrail:
    created_by: str
    action: str
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class Evidence:
    source: EvidenceSource | str
    kind: EvidenceKind | str
    payload: dict[str, Any]
    confidence: ConfidenceScore = field(default_factory=ConfidenceScore.medium)
    entity_id: str | None = None
    evidence_id: str = field(default_factory=lambda: f"ev-{uuid4().hex[:12]}")
    audit: list[AuditTrail] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.audit:
            self.audit.append(AuditTrail(created_by="hscad", action="evidence_created"))

    @property
    def source_value(self) -> str:
        return self.source.value if isinstance(self.source, Enum) else str(self.source)

    @property
    def kind_value(self) -> str:
        return self.kind.value if isinstance(self.kind, Enum) else str(self.kind)

    def add_audit(self, action: str, *, created_by: str = "hscad", **details: Any) -> None:
        self.audit.append(AuditTrail(created_by=created_by, action=action, details=details))

    def to_record(self) -> dict[str, Any]:
        return {
            "evidence_id": self.evidence_id,
            "entity_id": self.entity_id,
            "source": self.source_value,
            "kind": self.kind_value,
            "confidence": {
                "value": self.confidence.value,
                "reason": self.confidence.reason,
                "method": self.confidence.method,
            },
            "payload": self.payload,
            "audit": [
                {
                    "created_by": item.created_by,
                    "action": item.action,
                    "timestamp": item.timestamp,
                    "details": item.details,
                }
                for item in self.audit
            ],
            "tags": list(self.tags),
        }

    @classmethod
    def warning(cls, message: str, *, source: EvidenceSource | str = EvidenceSource.SYSTEM, **payload: Any) -> "Evidence":
        return cls(
            source=source,
            kind=EvidenceKind.WARNING,
            payload={"message": message, **payload},
            confidence=ConfidenceScore.high("system warning"),
            tags=["warning"],
        )

    @classmethod
    def error(cls, message: str, *, source: EvidenceSource | str = EvidenceSource.SYSTEM, **payload: Any) -> "Evidence":
        return cls(
            source=source,
            kind=EvidenceKind.ERROR,
            payload={"message": message, **payload},
            confidence=ConfidenceScore.high("system error"),
            tags=["error"],
        )


def evidence_from_mapping(data: Mapping[str, Any]) -> Evidence:
    confidence_data = data.get("confidence") or {}
    if isinstance(confidence_data, Mapping):
        confidence = ConfidenceScore(
            value=float(confidence_data.get("value", 0.5)),
            reason=str(confidence_data.get("reason", "")),
            method=str(confidence_data.get("method", "mapping")),
        )
    else:
        confidence = ConfidenceScore(float(confidence_data), method="mapping")
    return Evidence(
        evidence_id=str(data.get("evidence_id") or f"ev-{uuid4().hex[:12]}"),
        entity_id=data.get("entity_id"),
        source=data.get("source", EvidenceSource.SYSTEM),
        kind=data.get("kind", EvidenceKind.ENTITY),
        payload=dict(data.get("payload") or {}),
        confidence=confidence,
        tags=list(data.get("tags") or []),
    )
