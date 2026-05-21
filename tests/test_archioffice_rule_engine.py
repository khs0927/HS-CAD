# -*- coding: utf-8 -*-
"""
Unit tests for the ArchiOffice Rule Engine Framework
"""

import os
from pathlib import Path
from src.integrations.archioffice_rule_engine import ArchiOfficeRuleEngine

def test_archioffice_rule_engine_initialization():
    engine = ArchiOfficeRuleEngine()
    assert engine.ao_root == Path("C:\\Program Files\\ArchiOfficeZW2024")
    assert engine.is_loaded is False

def test_archioffice_rule_engine_load_flow():
    engine = ArchiOfficeRuleEngine()
    success = engine.load_all_rules()
    
    if Path("C:\\Program Files\\ArchiOfficeZW2024").exists():
        assert success is True
        assert engine.is_loaded is True
        
        # 1. 단축키 및 LISP 로드 검사
        assert len(engine.onekeys) > 0
        assert "PM" in engine.onekeys or "EA" in engine.onekeys or "T_KC" in engine.onekeys
        
        # 2. XPress 캐드 별칭 로드 검사
        assert len(engine.xpress_aliases) > 0
        assert "XEL" in engine.xpress_aliases or "XBM" in engine.xpress_aliases
        
        # 3. 강재 규격표 검사
        assert len(engine.steel_specs) > 0
        
        # 4. 실명 표준 리스트 검사
        assert len(engine.standard_rooms) > 0
        
        # 5. 프롬프트 생성 검사
        prompt = engine.generate_ao_drafting_prompt()
        assert "SYSTEM DRAFTING CONSTRAINTS" in prompt
        assert "ArchiOffice" in prompt
        assert "Shortkeys" in prompt or "단축키" in prompt
        assert "Steel" in prompt or "강재" in prompt
        
        # 6. JSON 영구 백업 검사
        out_path = "outputs/test_archioffice_rules.json"
        engine.export_rules_to_json(out_path)
        assert Path(out_path).exists()
        
        # Clean up
        if Path(out_path).exists():
            os.remove(out_path)
    else:
        assert success is False
