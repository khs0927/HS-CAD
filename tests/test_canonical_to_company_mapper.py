from src.company_profile.company_drafting_profile import CompanyDraftingProfile
from src.company_profile.canonical_to_company_mapper import map_canonical_to_company


def test_mapping_uses_profile():
    profile = CompanyDraftingProfile(
        titleblock_rules={"ZIUM_sheet_architect": {"confidence": 0.9}},
        dimension_rules={"300DIM": {"confidence": 0.9}},
        canonical_output_mapping=[
            {"canonical_element": "WALL", "candidate_layers": ["WAL1"]},
            {"canonical_element": "COLUMN", "candidate_layers": ["COL"]},
        ],
    )
    rec = map_canonical_to_company(situation_tag="판넬마감", canonical_elements=["WALL", "COLUMN"], profile=profile)
    layers = [r["layer"] for r in rec.recommended_company_layers]
    assert "WAL1" in layers
    assert "COL" in layers
    assert rec.recommended_dimension_style == "300DIM"
