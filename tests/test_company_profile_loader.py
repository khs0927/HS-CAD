from pathlib import Path

from src.company_profile.hs_cad_profile_loader import build_company_drafting_profile


def test_build_company_profile_from_docs(tmp_path: Path):
    (tmp_path / "docs").mkdir()
    (tmp_path / "README.md").write_text("ZIUM_sheet_architect WAL1 COL 중심선 치수 300DIM 지움EB 주변 속성", encoding="utf-8")
    profile = build_company_drafting_profile(tmp_path)
    assert profile.source_files
    assert profile.titleblock_rules
    assert profile.dimension_rules
    assert profile.layer_rules
