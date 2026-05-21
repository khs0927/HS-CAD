from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


class CompanyDraftingProfile(BaseModel):
    profile_id: str = "hs_cad_company_profile"
    source_files: list[str] = Field(default_factory=list)
    titleblock_rules: dict[str, Any] = Field(default_factory=dict)
    layer_rules: list[dict[str, Any]] = Field(default_factory=list)
    dimension_rules: dict[str, Any] = Field(default_factory=dict)
    text_style_rules: dict[str, Any] = Field(default_factory=dict)
    line_style_rules: dict[str, Any] = Field(default_factory=dict)
    block_reuse_rules: dict[str, Any] = Field(default_factory=dict)
    local_sampling_rules: dict[str, Any] = Field(default_factory=dict)
    preview_safety_rules: dict[str, Any] = Field(default_factory=dict)
    canonical_output_mapping: list[dict[str, Any]] = Field(default_factory=list)
    confidence: float = 0.0
    warnings: list[str] = Field(default_factory=list)

    def save(self, path: Path) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.model_dump_json(indent=2), encoding="utf-8")
        return path
