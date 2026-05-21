"""Pydantic models describing the company drafting profile.

The profile aggregates rules extracted from the repository – layers, title
blocks, dimensions, text styles, etc.  Each sub‑model includes a ``source``
field that records the file from which the rule was discovered and a
``confidence`` value that reflects how many sources agree on the rule.
"""

from __future__ import annotations

from typing import List, Optional, Dict

from pydantic import BaseModel, Field


class LayerRule(BaseModel):
    canonical_element: str = Field(..., description="Canonical element name, e.g. WALL")
    preferred_layer: Optional[str] = Field(None, description="Layer used in the company")
    aliases: List[str] = Field(default_factory=list)
    color: Optional[int] = Field(None)
    linetype: Optional[str] = Field(None)
    lineweight: Optional[int] = Field(None)
    source: Optional[str] = Field(None)
    confidence: float = Field(0.0)


class DimensionRule(BaseModel):
    preferred_dimension_layer: Optional[str] = Field(None)
    preferred_dimension_style: Optional[str] = Field(None)
    dimscale_policy: Optional[str] = Field(None)
    source: Optional[str] = Field(None)
    confidence: float = Field(0.0)


class TitleblockRule(BaseModel):
    preferred_titleblock_name: Optional[str] = Field(None)
    reuse_existing_block: bool = Field(True)
    source: Optional[str] = Field(None)
    confidence: float = Field(0.0)


class TextStyleRule(BaseModel):
    preferred_text_style: Optional[str] = Field(None)
    room_name_height: Optional[float] = Field(None)
    general_note_height: Optional[float] = Field(None)
    title_height: Optional[float] = Field(None)
    scale_policy: Optional[str] = Field(None)
    source: Optional[str] = Field(None)
    confidence: float = Field(0.0)


class CompanyDraftingProfile(BaseModel):
    profile_id: str = Field("hs_cad_company_profile", description="Fixed identifier")
    source_files: List[str] = Field(default_factory=list)
    layer_rules: List[LayerRule] = Field(default_factory=list)
    dimension_rules: List[DimensionRule] = Field(default_factory=list)
    titleblock_rules: List[TitleblockRule] = Field(default_factory=list)
    text_style_rules: List[TextStyleRule] = Field(default_factory=list)
    # Additional rule collections can be added later
    confidence: float = Field(0.0)
    warnings: List[str] = Field(default_factory=list)
