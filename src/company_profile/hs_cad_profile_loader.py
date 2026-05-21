from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path

from .company_drafting_profile import CompanyDraftingProfile
from .docs_profile_extractor import extract_rules_from_text


PROFILE_GLOBS = [
    "README.md",
    "docs/*.md",
    "examples/**/*.json",
    "generated/**/*.json",
    "tools/**/*.py",
    "tests/**/*.py",
    "src/**/*.py",
]


def discover_profile_sources(repo_root: Path) -> list[Path]:
    repo_root = Path(repo_root)
    sources: list[Path] = []
    for pattern in PROFILE_GLOBS:
        sources.extend([p for p in repo_root.glob(pattern) if p.is_file()])
    return sorted(set(sources))


def build_company_drafting_profile(repo_root: Path, out_dir: Path | None = None) -> CompanyDraftingProfile:
    repo_root = Path(repo_root)
    rules_by_type: dict[str, list] = defaultdict(list)
    source_files: list[str] = []

    for path in discover_profile_sources(repo_root):
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        extracted = extract_rules_from_text(path.relative_to(repo_root), text)
        if extracted:
            source_files.append(str(path.relative_to(repo_root)))
        for rule in extracted:
            rules_by_type[rule.rule_type].append(rule)

    profile = CompanyDraftingProfile(source_files=sorted(set(source_files)))
    profile.titleblock_rules = _best_values(rules_by_type.get("titleblock", []))
    profile.dimension_rules = _best_values(rules_by_type.get("dimension", []))
    profile.text_style_rules = _best_values(rules_by_type.get("text_style", []))
    profile.preview_safety_rules = _best_values(rules_by_type.get("policy", []))

    layer_counts = _best_values(rules_by_type.get("layer", []))
    for value, info in layer_counts.items():
        profile.layer_rules.append(
            {
                "preferred_layer": value,
                "source": info.get("source"),
                "evidence_text": info.get("evidence_text"),
                "confidence": info.get("confidence", 0.0),
            }
        )

    profile.canonical_output_mapping = _default_mapping_from_profile(profile)
    profile.confidence = min(1.0, 0.2 + 0.1 * len(profile.source_files))
    if not profile.source_files:
        profile.warnings.append("No HS-CAD company profile sources found.")

    if out_dir:
        out_path = Path(out_dir) / "company_drafting_profile.json"
        profile.save(out_path)
    return profile


def _best_values(rules: list) -> dict:
    counter = Counter([r.value for r in rules])
    out = {}
    for value, count in counter.most_common():
        rule = next(r for r in rules if r.value == value)
        out[value] = {
            "count": count,
            "source": rule.source_file,
            "evidence_text": rule.evidence_text,
            "confidence": min(0.95, 0.5 + 0.1 * count),
        }
    return out


def _default_mapping_from_profile(profile: CompanyDraftingProfile) -> list[dict]:
    layer_values = {r.get("preferred_layer", "") for r in profile.layer_rules}
    mappings: list[dict] = []

    def add(canonical: str, candidates: list[str]):
        found = [c for c in candidates if c in layer_values]
        mappings.append({"canonical_element": canonical, "candidate_layers": found or candidates, "source": "company_profile"})

    add("WALL", ["WAL1", "WALL1"])
    add("COLUMN", ["COL", "COLU"])
    add("CENTERLINE", ["중심선", "CEN"])
    add("DIMENSION", ["치수", "DIM"])
    return mappings
