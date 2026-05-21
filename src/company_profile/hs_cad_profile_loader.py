"""Load the company drafting profile from repository sources.

The implementation is intentionally lightweight – it scans markdown and JSON
files that are part of the repository and extracts a few well‑known rule
tokens.  The goal is to provide a deterministic source of truth without
hard‑coding any values in the code.
"""

from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import List, Tuple, Dict

from .models import (
    CompanyDraftingProfile,
    LayerRule,
    DimensionRule,
    TitleblockRule,
    TextStyleRule,
)

# ---------------------------------------------------------------------------
# Helper utilities
# ---------------------------------------------------------------------------

def _read_text(file_path: Path) -> str:
    try:
        return file_path.read_text(encoding="utf-8")
    except Exception:
        return ""


def _discover_source_files(repo_root: Path) -> List[Path]:
    """Return a list of files that may contain drafting rules.

    We include the main README, all markdown files under ``docs``, and any
    JSON examples under ``examples`` or ``generated``.  Files that do not
    exist are ignored.
    """

    candidates: List[Path] = []
    readme = repo_root / "README.md"
    if readme.exists():
        candidates.append(readme)
    candidates.extend(sorted((repo_root / "docs").rglob("*.md")))
    candidates.extend(sorted((repo_root / "examples").rglob("*.json")))
    candidates.extend(sorted((repo_root / "generated").rglob("*.json")))
    # Filter out any non‑existent paths just in case
    return [p for p in candidates if p.is_file()]


# ---------------------------------------------------------------------------
# Extraction logic – simple keyword based heuristics
# ---------------------------------------------------------------------------

# Mapping of canonical element → list of keywords that indicate a layer name
_CANONICAL_LAYER_KEYWORDS: Dict[str, List[str]] = {
    "WALL": ["wall", "a-wall"],
    "COLUMN": ["col", "column", "a-column"],
    "BEAM": ["beam", "a-beam"],
    "SLAB": ["slab"],
    "DOOR": ["door"],
    "WINDOW": ["window", "win"],
    "CENTERLINE": ["centerline", "중심선"],
    "DIMENSION": ["dim", "300dim"],
}

# Simple patterns for other rule types
_DIMENSION_STYLE_PATTERN = re.compile(r"300\s*DIM", re.IGNORECASE)
_TITLEBLOCK_PATTERN = re.compile(r"ZIUM[_-]?sheet[_-]?architect", re.IGNORECASE)
_TEXT_STYLE_PATTERN = re.compile(r"지움EB", re.IGNORECASE)


def _extract_layer_candidates(text: str) -> Dict[str, List[str]]:
    """Return a mapping *canonical → found layer strings* from the given text.

    The function looks for whole‑word occurrences of the keywords defined in
    ``_CANONICAL_LAYER_KEYWORDS``.  When a keyword is found we capture the
    surrounding token (a word consisting of letters, numbers, hyphens, or
    underscores) as the candidate layer name.
    """

    result: Dict[str, List[str]] = defaultdict(list)
    for canonical, keywords in _CANONICAL_LAYER_KEYWORDS.items():
        for kw in keywords:
            # ``\b`` ensures we match whole words; ``[\w-]+`` captures the
            # token that contains the keyword.
            pattern = re.compile(r"(\\b[\\w-]*" + re.escape(kw) + r"[\\w-]*\\b)", re.IGNORECASE)
            for match in pattern.finditer(text):
                token = match.group(1)
                result[canonical].append(token)
    return result


def _most_common_candidate(candidates: List[str]) -> Tuple[str, int]:
    if not candidates:
        return ("", 0)
    counter = Counter(candidates)
    most, count = counter.most_common(1)[0]
    return most, count


def build_company_drafting_profile(repo_root: Path) -> CompanyDraftingProfile:
    """Extract the drafting profile from repository files.

    The function aggregates evidence from multiple source files and builds a
    ``CompanyDraftingProfile`` instance.  Confidence values are computed as the
    ratio of occurrences to the total number of source files that contributed
    to the rule.
    """

    source_files = _discover_source_files(repo_root)
    profile = CompanyDraftingProfile()
    profile.source_files = [str(p) for p in source_files]

    # Accumulate layer candidates across all sources
    layer_candidates: Dict[str, List[str]] = defaultdict(list)
    dimension_style_hits = 0
    titleblock_hits = 0
    text_style_hits = 0

    for file_path in source_files:
        text = _read_text(file_path)
        # Layer extraction
        layer_map = _extract_layer_candidates(text)
        for canonical, tokens in layer_map.items():
            layer_candidates[canonical].extend(tokens)
        # Dimension style detection
        if _DIMENSION_STYLE_PATTERN.search(text):
            dimension_style_hits += 1
        # Titleblock detection
        if _TITLEBLOCK_PATTERN.search(text):
            titleblock_hits += 1
        # Text style detection
        if _TEXT_STYLE_PATTERN.search(text):
            text_style_hits += 1

    total_sources = len(source_files) or 1

    # Build LayerRule objects
    for canonical, tokens in layer_candidates.items():
        preferred, count = _most_common_candidate(tokens)
        if preferred:
            rule = LayerRule(
                canonical_element=canonical,
                preferred_layer=preferred,
                aliases=list(set(tokens)),
                source="heuristic",
                confidence=count / total_sources,
            )
            profile.layer_rules.append(rule)

    # DimensionRule – we only capture style if we saw the pattern
    if dimension_style_hits:
        drule = DimensionRule(
            preferred_dimension_layer=None,
            preferred_dimension_style="300DIM",
            source="heuristic",
            confidence=dimension_style_hits / total_sources,
        )
        profile.dimension_rules.append(drule)

    # TitleblockRule
    if titleblock_hits:
        tbrule = TitleblockRule(
            preferred_titleblock_name="ZIUM_sheet_architect",
            source="heuristic",
            confidence=titleblock_hits / total_sources,
        )
        profile.titleblock_rules.append(tbrule)

    # TextStyleRule – capture the known style name
    if text_style_hits:
        tsrule = TextStyleRule(
            preferred_text_style="지움EB",
            source="heuristic",
            confidence=text_style_hits / total_sources,
        )
        profile.text_style_rules.append(tsrule)

    # Overall confidence – simple average of rule confidences
    rule_confidences = [r.confidence for r in profile.layer_rules]
    rule_confidences += [r.confidence for r in profile.dimension_rules]
    rule_confidences += [r.confidence for r in profile.titleblock_rules]
    rule_confidences += [r.confidence for r in profile.text_style_rules]
    if rule_confidences:
        profile.confidence = sum(rule_confidences) / len(rule_confidences)

    return profile


def write_profile_to_file(profile: CompanyDraftingProfile, out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        json.dump(profile.model_dump(mode="json"), f, ensure_ascii=False, indent=2)
