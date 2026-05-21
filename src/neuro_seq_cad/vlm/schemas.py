from __future__ import annotations

from pydantic import BaseModel, Field


class VLMCorrection(BaseModel):
    type: str
    target_ids: list[str] = Field(default_factory=list)
    reason: str
    confidence: float = Field(ge=0.0, le=1.0)


class VLMWarning(BaseModel):
    type: str
    message: str
    target_ids: list[str] = Field(default_factory=list)


class VLMRefinementResult(BaseModel):
    corrections: list[VLMCorrection] = Field(default_factory=list)
    warnings: list[VLMWarning] = Field(default_factory=list)

