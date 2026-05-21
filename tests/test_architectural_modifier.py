# -*- coding: utf-8 -*-
"""
Unit tests for the upgraded Architectural Modifier (Rules-Based Action Builders)
"""

import pytest
from pathlib import Path
from src.modifiers.architectural_modifier import (
    create_xicad_wall_actions,
    create_steel_beam_actions,
    insert_spec_block_actions
)
from src.integrations.xicad_rule_engine import XiCADRuleEngine
from src.integrations.archioffice_rule_engine import ArchiOfficeRuleEngine

@pytest.fixture
def xicad_engine():
    engine = XiCADRuleEngine()
    engine.load_all_rules()
    return engine

@pytest.fixture
def archioffice_engine():
    engine = ArchiOfficeRuleEngine()
    engine.load_all_rules()
    return engine

def test_create_xicad_wall_actions(xicad_engine):
    # 1. 200mm 일반 벽체 스타일 테스트 (가상 또는 실데이터)
    actions = create_xicad_wall_actions(
        engine=xicad_engine,
        group_name="기본벽",
        length=5000.0,
        direction="horizontal",
        origin=(100, 100, 0)
    )
    
    assert len(actions) > 0
    for act in actions:
        assert act["action"] == "create_polyline"
        assert "A-WALL" in act["layer"]
        assert len(act["points"]) == 2
        # Y좌표가 오프셋에 따라 배치되었는지 검증
        assert act["points"][0][0] == 100.0
        assert act["points"][1][0] == 5100.0

def test_create_steel_beam_actions_xicad(xicad_engine):
    # 2. XiCAD H형강 규격을 활용한 작도 액션 테스트
    actions = create_steel_beam_actions(
        engine=xicad_engine,
        is_xicad=True,
        steel_type="H형강",
        spec_name="200x200",
        origin=(0, 0, 0)
    )
    
    assert len(actions) > 0
    assert actions[0]["action"] == "create_polyline"
    assert actions[0]["closed"] is True
    # H형강의 정교한 12점 닫힌 외곽선 좌표인지 확인
    assert len(actions[0]["points"]) == 13

def test_create_steel_beam_actions_archioffice(archioffice_engine):
    # 3. ArchiOffice 각관 규격을 활용한 작도 액션 테스트
    if Path("C:\\Program Files\\ArchiOfficeZW2024").exists():
        actions = create_steel_beam_actions(
            engine=archioffice_engine,
            is_xicad=False,
            steel_type="각형강관",
            spec_name="100x100",
            origin=(10, 10, 0)
        )
        
        assert len(actions) > 0
        assert actions[0]["action"] == "create_polyline"
        assert actions[0]["closed"] is True
        # 각관 단면 (5점 닫힌 사각형 루프)
        assert len(actions[0]["points"]) == 5

def test_insert_spec_block_actions(xicad_engine, archioffice_engine):
    # 4. 규격 블록 삽입 레이어 자동 매핑 테스트 (XiCAD)
    xicad_actions = insert_spec_block_actions(
        engine=xicad_engine,
        is_xicad=True,
        category="가구",
        block_name="I_SOFA_1",
        origin=(500, 500, 0)
    )
    assert len(xicad_actions) == 1
    assert xicad_actions[0]["action"] == "insert_block"
    assert xicad_actions[0]["block_name"] == "I_SOFA_1"
    assert "SYM" in xicad_actions[0]["layer"]

    # 5. 규격 블록 삽입 레이어 자동 매핑 테스트 (ArchiOffice)
    if Path("C:\\Program Files\\ArchiOfficeZW2024").exists():
        ao_actions = insert_spec_block_actions(
            engine=archioffice_engine,
            is_xicad=False,
            category="조경",
            block_name="TREE_01",
            origin=(1000, 1000, 0)
        )
        assert len(ao_actions) == 1
        assert ao_actions[0]["action"] == "insert_block"
        assert "SYM" in ao_actions[0]["layer"]
