# -*- coding: utf-8 -*-
"""Unit tests for HSSteelRuleEngine."""
import pytest
from src.integrations.hssteel_rule_engine import HSSteelRuleEngine

@pytest.fixture
def mock_hssteel_dir(tmp_path):
    # Create support dir and pgp file
    support_dir = tmp_path / "support"
    support_dir.mkdir()
    pgp_file = support_dir / "hssteel.pgp"
    pgp_file.write_text("RCC, *SOL-GB-CHK-RC\nHHH, *HS-SHAPE-HIDDEN-LINE-ADD\n", encoding="utf-8")
    
    # Create block dir and dwg files
    block_dir = tmp_path / "block"
    block_dir.mkdir()
    (block_dir / "DK기성품_C100x4-5T.dwg").touch()
    (block_dir / "WELD_개선.dwg").touch()
    
    return tmp_path

def test_hssteel_engine_load(mock_hssteel_dir):
    engine = HSSteelRuleEngine(base_dir=str(mock_hssteel_dir))
    engine.load_all()
    
    assert engine.is_loaded is True
    aliases = engine.get_aliases()
    
    # Verify exact alias parsed from support/hssteel.pgp
    assert "RCC" in aliases
    assert aliases["RCC"] == "SOL-GB-CHK-RC"
    assert aliases["HHH"] == "HS-SHAPE-HIDDEN-LINE-ADD"

def test_hssteel_block_catalog(mock_hssteel_dir):
    engine = HSSteelRuleEngine(base_dir=str(mock_hssteel_dir))
    engine.load_all()
    
    catalog = engine.get_block_catalog()
    assert "all_blocks" in catalog
    assert catalog["total_count"] > 0
    
    # Check if categorized structure exists
    assert "기성품" in catalog["categorized"]
    assert "weld" in catalog["categorized"]
    
    # DK기성품_C100x4-5T should be present or classified
    assert any("기성품" in b for b in catalog["all_blocks"])
