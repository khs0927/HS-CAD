"""Text role inference for room names, dimensions and notes."""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from hscad.core.evidence import Evidence, make_evidence
from hscad.core.models import DrawingEntity, FileizedDrawing

_DIM_RE = re.compile(r"^\s*\d+(?:\.\d+)?\s*(?:m|mm|㎡|m2|M2)?\s*$", re.IGNORECASE)
_ROOM_WORDS = ("실", "ROOM", "OFFICE", "HALL", "창고", "화장실", "복도", "기계", "전기")


@dataclass(frozen=True)
class TextRole:
    entity_id: str
    text: str
    role: str
    confidence: float
    reason: str

    def to_record(self) -> dict[str, Any]:
        return self.__dict__.copy()


@dataclass(frozen=True)
class TextRoleAnalysis:
    roles: list[TextRole]
    evidence: list[Evidence]

    def to_record(self) -> dict[str, Any]:
        return {"roles": [r.to_record() for r in self.roles], "evidence": [e.to_record() for e in self.evidence]}


class TextRoleAnalyzer:
    def analyze(self, drawing: FileizedDrawing) -> TextRoleAnalysis:
        roles: list[TextRole] = []
        for ent in drawing.entities:
            if ent.entity_type.upper() not in {"TEXT", "MTEXT"} or not ent.text:
                continue
            role, conf, reason = self._classify(ent.text)
            roles.append(TextRole(ent.entity_id, ent.text, role, conf, reason))
        evidence = [make_evidence("analyzer.text_role.summary", "text_role_inference", f"Classified {len(roles)} text entities", module="hscad.analyzers.text_role_analyzer", source_id=drawing.input_path, confidence=0.85 if roles else 0.25, data={"roles": [r.to_record() for r in roles]})]
        return TextRoleAnalysis(roles, evidence)

    def _classify(self, text: str) -> tuple[str, float, str]:
        t = text.strip()
        if not t:
            return "empty", 0.1, "blank text"
        if _DIM_RE.match(t):
            return "dimension_or_area", 0.72, "numeric dimension/area pattern"
        if any(word.lower() in t.lower() for word in _ROOM_WORDS):
            return "room_name", 0.74, "room keyword"
        if len(t) <= 12 and any(ch.isalpha() or "가" <= ch <= "힣" for ch in t):
            return "label", 0.55, "short text label"
        return "note", 0.45, "fallback note"
