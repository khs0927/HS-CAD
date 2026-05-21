# -*- coding: utf-8 -*-
"""
Unit tests for the XiCAD Rule Engine Framework (v2)
"""

import os
from pathlib import Path
from src.integrations.xicad_rule_engine import XiCADRuleEngine

def test_xicad_rule_engine_v2_initialization():
    engine = XiCADRuleEngine("C:\\xicad")
    assert engine.xicad_root == Path("C:\\xicad")
    assert engine.is_loaded is False

def test_xicad_rule_engine_v2_load_flow():
    engine = XiCADRuleEngine("C:\\xicad")
    success = engine.load_all_rules()
    
    if Path("C:\\xicad").exists():
        assert success is True
        assert engine.is_loaded is True
        
        # 1. 기존 벽체 및 블록 룰셋 검증
        assert len(engine.wall_styles) > 0
        assert len(engine.block_layer_rules) > 0
        
        # 2. 신규 확장 파서 검증
        assert len(engine.shortkeys) > 0
        assert len(engine.pgp_aliases) > 0
        assert len(engine.structural_steel_specs) > 0
        assert "h_beam" in engine.structural_steel_specs
        assert "square_pipe" in engine.structural_steel_specs
        
        # 3. 블록 라이브러리 검증
        assert engine.block_catalog.get("total_blocks", 0) > 0
        
        # 4. 프롬프트 생성 검증
        prompt = engine.generate_ai_drafting_prompt()
        assert "SYSTEM DRAFTING CONSTRAINTS" in prompt
        assert "H-Beam" in prompt or "H_BEAM" in prompt or "강재" in prompt
        assert "SHORTCUT MAPPING" in prompt or "단축키" in prompt
        assert "블록" in prompt or "Library" in prompt
        
        # 5. JSON 영구 내보내기 검증
        out_path = "outputs/test_xicad_rules_v2.json"
        engine.export_rules_to_json(out_path)
        assert Path(out_path).exists()
        
        # Clean up
        if Path(out_path).exists():
            os.remove(out_path)
    else:
        assert success is False
