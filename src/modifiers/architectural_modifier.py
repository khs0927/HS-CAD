# -*- coding: utf-8 -*-
from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any, Iterable
import yaml
from pathlib import Path

# XiCAD & ArchiOffice 룰 엔진 연동을 위한 안전 임포트
try:
    from src.integrations.xicad_rule_engine import XiCADRuleEngine
    from src.integrations.archioffice_rule_engine import ArchiOfficeRuleEngine
except ImportError:
    # 패스 백업 (테스트 구동용)
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from src.integrations.xicad_rule_engine import XiCADRuleEngine
    from src.integrations.archioffice_rule_engine import ArchiOfficeRuleEngine

def _load_config_layers() -> set[str]:
    default_layers = {
        'A-WALL', 'A-COLUMN', 'A-BEAM', 'A-SLAB', 'A-DOOR', 'A-WINDOW',
        'A-ROOM', 'A-TEXT', 'A-DIMS', 'A-GRID', 'A-BOUNDARY', 'A-XICAD'
    }
    try:
        config_path = Path(__file__).resolve().parents[2] / 'config' / 'layer_rules.yaml'
        if config_path.exists():
            with open(config_path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)
                if data and 'architecture_layers' in data:
                    all_patterns = set()
                    for key, patterns in data['architecture_layers'].items():
                        for p in patterns:
                            all_patterns.add(p.upper())
                    return all_patterns
    except Exception:
        pass
    return default_layers

ARCH_LAYERS = _load_config_layers()

def _origin3(origin: tuple[float, float, float] | list[float] = (0, 0, 0)) -> tuple[float, float, float]:
    vals = list(origin) + [0, 0, 0]
    return float(vals[0]), float(vals[1]), float(vals[2])

def create_boundary(width: float, depth: float, origin: tuple[float,float,float]=(0,0,0), layer: str='A-BOUNDARY') -> list[dict[str, Any]]:
    x, y, z = _origin3(origin)
    pts = [[x,y,z],[x+width,y,z],[x+width,y+depth,z],[x,y+depth,z],[x,y,z]]
    return [{'action':'create_polyline','layer':layer,'closed':True,'points':pts}]

def create_grid(width: float, depth: float, grid_x: float, grid_y: float, origin: tuple[float,float,float]=(0,0,0), layer: str='A-GRID') -> list[dict[str, Any]]:
    x0, y0, z = _origin3(origin)
    actions: list[dict[str, Any]] = []
    ix = 0
    x = 0.0
    while x <= width + 1e-6:
        actions.append({'action':'create_line','layer':layer,'name':f'X{ix+1}','start':[x0+x,y0,z],'end':[x0+x,y0+depth,z]})
        ix += 1
        x += grid_x
    iy = 0
    y = 0.0
    while y <= depth + 1e-6:
        actions.append({'action':'create_line','layer':layer,'name':f'Y{iy+1}','start':[x0,y0+y,z],'end':[x0+width,y0+y,z]})
        iy += 1
        y += grid_y
    return actions

def place_columns(block_name: str, width: float, depth: float, grid_x: float, grid_y: float, origin: tuple[float,float,float]=(0,0,0), layer: str='A-COLUMN') -> list[dict[str, Any]]:
    x0, y0, z = _origin3(origin)
    actions: list[dict[str, Any]] = []
    x = 0.0
    while x <= width + 1e-6:
        y = 0.0
        while y <= depth + 1e-6:
            actions.append({'action':'insert_block','block_name':block_name,'layer':layer,'insert':[x0+x,y0+y,z],'rotation':0,'scale':[1,1,1]})
            y += grid_y
        x += grid_x
    return actions

def place_beams_2d(width: float, depth: float, grid_x: float, grid_y: float, origin: tuple[float,float,float]=(0,0,0), layer: str='A-BEAM') -> list[dict[str, Any]]:
    x0, y0, z = _origin3(origin)
    actions: list[dict[str, Any]] = []
    x = 0.0
    while x <= width + 1e-6:
        actions.append({'action':'create_line','layer':layer,'name':f'BX{x:g}','start':[x0+x,y0,z],'end':[x0+x,y0+depth,z]})
        x += grid_x
    y = 0.0
    while y <= depth + 1e-6:
        actions.append({'action':'create_line','layer':layer,'name':f'BY{y:g}','start':[x0,y0+y,z],'end':[x0+width,y0+y,z]})
        y += grid_y
    return actions

# =========================================================================
# 🔴 [RULES-BASED DRAFTING ACTION BUILDERS UPGRADE]
# =========================================================================

def create_xicad_wall_actions(
    engine: XiCADRuleEngine, 
    group_name: str, 
    length: float, 
    direction: str = "horizontal",
    origin: tuple[float, float, float] = (0, 0, 0)
) -> list[dict[str, Any]]:
    """
    XiCAD에서 추출된 다중선 벽체 스타일 사양을 바탕으로 
    실제 CAD 도면에 레이어 및 오프셋 두께를 정확히 적용한 Polyline 벽체 액션들을 조립합니다.
    """
    if not engine.is_loaded:
        engine.load_all()
        
    # 일치하는 그룹 탐색
    style_data = None
    for name, data in engine.wall_styles.items():
        if group_name.lower() in name.lower():
            style_data = data
            break
            
    if not style_data:
        # Fallback: 스타일을 찾지 못하면 200mm 일반 벽체 액션 반환
        style_data = {
            "lines": [
                {"offset": -100.0, "layer": "A-WALL", "linetype": "Continuous", "color": 4},
                {"offset": 100.0, "layer": "A-WALL", "linetype": "Continuous", "color": 4}
            ]
        }

    x0, y0, z = _origin3(origin)
    actions = []
    
    # 스타일 내 개별 오프셋 라인들을 Polyline으로 생성
    for idx, l in enumerate(style_data.get("lines", [])):
        offset = l["offset"]
        layer_name = f"A-WALL-{l['layer']}" if l['layer'] != '0' else 'A-WALL'
        
        if direction.lower() == "horizontal":
            pts = [
                [x0, y0 + offset, z],
                [x0 + length, y0 + offset, z]
            ]
        else:
            pts = [
                [x0 + offset, y0, z],
                [x0 + offset, y0 + length, z]
            ]
            
        actions.append({
            'action': 'create_polyline',
            'layer': layer_name,
            'closed': False,
            'points': pts,
            'name': f"WallLine_{idx}"
        })
        
    return actions

def create_steel_beam_actions(
    engine: Any, 
    is_xicad: bool,
    steel_type: str, 
    spec_name: str, 
    origin: tuple[float, float, float] = (0, 0, 0)
) -> list[dict[str, Any]]:
    """
    XiCAD (.dat) 혹은 ArchiOffice (ShapeSteel.txt) 형강 치수 규격 테이블을 조회하여 
    H형강, 각관 등의 정확한 단면(H-Beam Cross Section)을 그릴 수 있는 Polyline 액션들을 구축합니다.
    """
    if not engine.is_loaded:
        engine.load_all()

    spec = None
    if is_xicad:
        # XiCAD spec search
        specs = engine.structural_steel_specs.get(steel_type, [])
        for s in specs:
            if spec_name.lower() in s["name"].lower():
                spec = s
                break
    else:
        # ArchiOffice spec search
        for cat, items in engine.steel_specs.items():
            if steel_type.lower() in cat.lower() or "형강" in cat.lower() or "pipe" in cat.lower():
                for item in items:
                    if spec_name.lower() in item["name"].lower():
                        spec = item
                        break
                if spec:
                    break

    if not spec:
        # Fallback: 200x200 H형강
        spec = {
            "height": 200.0, "width": 200.0, 
            "web_thickness": 8.0, "flange_thickness": 12.0
        }

    x, y, z = _origin3(origin)
    h = spec.get("height", spec.get("width", 200.0))
    w = spec.get("width", 200.0)
    
    actions = []
    
    if "web_thickness" in spec and "flange_thickness" in spec:
        # 1. H형강 단면 그리기 (정교한 12점 외곽선 Polyline)
        tw = spec["web_thickness"]
        tf = spec["flange_thickness"]
        
        # 중심 정렬 단면 좌표 계산
        pts = [
            [x - w/2, y + h/2, z],                          # Top Left Outer
            [x + w/2, y + h/2, z],                          # Top Right Outer
            [x + w/2, y + h/2 - tf, z],                     # Top Right Inner-Flange
            [x + tw/2, y + h/2 - tf, z],                    # Top Right Inner-Web
            [x + tw/2, y - h/2 + tf, z],                    # Bottom Right Inner-Web
            [x + w/2, y - h/2 + tf, z],                     # Bottom Right Inner-Flange
            [x + w/2, y - h/2, z],                          # Bottom Right Outer
            [x - w/2, y - h/2, z],                          # Bottom Left Outer
            [x - w/2, y - h/2 + tf, z],                     # Bottom Left Inner-Flange
            [x - tw/2, y - h/2 + tf, z],                    # Bottom Left Inner-Web
            [x - tw/2, y + h/2 - tf, z],                    # Top Left Inner-Web
            [x - w/2, y + h/2 - tf, z],                     # Top Left Inner-Flange
            [x - w/2, y + h/2, z]                           # Close loop
        ]
        actions.append({
            'action': 'create_polyline',
            'layer': 'A-BEAM-STEEL',
            'closed': True,
            'points': pts,
            'name': f"H_Beam_{spec_name}"
        })
    else:
        # 2. 각관 단면 (Closed Rectangle)
        pts = [
            [x - w/2, y + h/2, z],
            [x + w/2, y + h/2, z],
            [x + w/2, y - h/2, z],
            [x - w/2, y - h/2, z],
            [x - w/2, y + h/2, z]
        ]
        actions.append({
            'action': 'create_polyline',
            'layer': 'A-BEAM-STEEL',
            'closed': True,
            'points': pts,
            'name': f"Box_Beam_{spec_name}"
        })
        
    return actions

def insert_spec_block_actions(
    engine: Any,
    is_xicad: bool | str,  # "hssteel" 문자열이나 True/False 처리 지원
    category: str,
    block_name: str,
    origin: tuple[float, float, float] = (0, 0, 0)
) -> list[dict[str, Any]]:
    """
    XiCAD, ArchiOffice 또는 HSSTEEL의 라이브러리 블록 삽입 액션을 빌드하며,
    각 가구/구조/위생 카테고리에 정의된 공식 레이어를 자동 매핑 및 격리 부여합니다.
    """
    if not engine.is_loaded:
        engine.load_all()

    layer = "A-XICAD-SYM"
    
    if is_xicad == "hssteel" or "HSSteel" in type(engine).__name__:
        # HSSTEEL Structural symbols layer
        layer = f"A-HSSTEEL-SYM-{category.upper()}"
    elif is_xicad is True:
        # XiCAD Blk Layer mapping
        rule = engine.block_layer_rules.get(category)
        if rule:
            layer = f"A-SYM-{rule['layer']}"
    else:
        # ArchiOffice Category mapping
        layer = f"A-AO-SYM-{category.upper()}"

    x, y, z = _origin3(origin)
    return [{
        'action': 'insert_block',
        'block_name': block_name,
        'layer': layer,
        'insert': [x, y, z],
        'rotation': 0,
        'scale': [1.0, 1.0, 1.0]
    }]

def create_hybrid_structure_actions(
    xicad_engine: XiCADRuleEngine,
    ao_engine: ArchiOfficeRuleEngine,
    wall_style: str,
    steel_spec: str,
    length: float,
    origin: tuple[float, float, float] = (0, 0, 0)
) -> list[dict[str, Any]]:
    """
    XiCAD의 다중선 벽체와 ArchiOffice의 정밀 철골 규격을 융합하여,
    외단열 벽체 내부에 철골(기둥)이 삽입된 복합 구조를 단 한 번에 작도합니다.
    """
    actions = []
    
    # 1. ArchiOffice 규격을 참조한 H빔/각관 중앙 기둥 세우기
    actions.extend(create_steel_beam_actions(
        engine=ao_engine, 
        is_xicad=False, 
        steel_type="H형강", 
        spec_name=steel_spec, 
        origin=origin
    ))
    
    # 2. XiCAD 규격을 참조한 외벽 다중선(단열재+마감)으로 기둥 감싸기
    # 벽체를 기둥 중심축을 기준으로 위아래 대칭 혹은 외측으로 생성
    actions.extend(create_xicad_wall_actions(
        engine=xicad_engine,
        group_name=wall_style,
        length=length,
        direction="horizontal",
        origin=origin
    ))
    
    return actions

# =========================================================================

def execute_planned_actions(adapter: Any, actions: list[dict[str, Any]]) -> dict[str, Any]:
    created = 0
    errors: list[dict[str, Any]] = []
    for action in actions:
        try:
            kind = action.get('action')
            if kind == 'create_line':
                adapter.create_line(action['start'], action['end'], action.get('layer', '0'))
                created += 1
            elif kind == 'create_polyline':
                adapter.create_polyline(action['points'], action.get('layer', '0'), action.get('closed', True))
                created += 1
            elif kind == 'insert_block':
                adapter.insert_block(action['block_name'], action['insert'], action.get('layer', '0'), action.get('rotation', 0), action.get('scale', [1,1,1]))
                created += 1
            else:
                errors.append({'action': action, 'error': f'Unsupported planned action: {kind}'})
        except Exception as exc:
            errors.append({'action': action, 'error': str(exc)})
    return {'created': created, 'errors': errors, 'planned': len(actions)}

def scan_architecture_layers(objects: Iterable[dict[str, Any]]) -> dict[str, Any]:
    counts: Counter[str] = Counter()
    candidates: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for obj in objects:
        layer = str(obj.get('layer') or '')
        if layer:
            counts[layer] += 1
        up = layer.upper()
        for arch in ARCH_LAYERS:
            if up == arch or up.startswith(arch + '-') or arch in up:
                candidates[arch].append(obj)
    return {'layer_counts': dict(counts), 'architecture_layer_counts': {k: len(v) for k, v in candidates.items()}, 'known_arch_layers': sorted(ARCH_LAYERS)}

def extract_room_texts(objects: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    keywords = ['ROOM', 'AREA', '실', '면적', 'A-ROOM', '평면', '글씨']
    try:
        config_path = Path(__file__).resolve().parents[2] / 'config' / 'layer_rules.yaml'
        if config_path.exists():
            with open(config_path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)
                if data and 'architecture_layers' in data:
                    text_patterns = data['architecture_layers'].get('text', [])
                    for p in text_patterns:
                        keywords.append(p.upper())
    except Exception:
        pass
        
    for obj in objects:
        text = obj.get('text')
        layer = str(obj.get('layer') or '')
        if text and (any(k.upper() in layer.upper() for k in keywords) or any(k in str(text) for k in ('㎡','m2','실','호'))):
            rows.append({'handle': obj.get('handle'), 'layer': layer, 'text': text, 'insert': obj.get('insert')})
    return rows

def check_closed_polylines(objects: Iterable[dict[str, Any]]) -> dict[str, Any]:
    total = 0
    closed = 0
    open_items: list[dict[str, Any]] = []
    for obj in objects:
        if str(obj.get('entity_type') or obj.get('object_name') or '').upper().find('POLYLINE') >= 0:
            total += 1
            is_closed = bool(obj.get('closed'))
            if is_closed:
                closed += 1
            else:
                open_items.append({'handle': obj.get('handle'), 'layer': obj.get('layer')})
    return {'polyline_count': total, 'closed_count': closed, 'open_count': total - closed, 'open_candidates': open_items[:200]}

def generate_architecture_summary(objects: list[dict[str, Any]]) -> dict[str, Any]:
    entity_counts = Counter(str(o.get('entity_type') or o.get('object_name') or 'UNKNOWN') for o in objects)
    block_counts = Counter(str(o.get('effective_name') or o.get('name')) for o in objects if o.get('effective_name') or o.get('name'))
    return {
        'object_count': len(objects),
        'entity_counts': dict(entity_counts),
        'architecture_layers': scan_architecture_layers(objects),
        'room_texts': extract_room_texts(objects),
        'polyline_quality': check_closed_polylines(objects),
        'block_counts': dict(block_counts),
    }

def prepare_for_xicad_wall(objects: list[dict[str, Any]]) -> dict[str, Any]:
    return {'workflow': 'wall_basic', 'recommended_alias': 'WAL', 'precheck': scan_architecture_layers(objects), 'interactive_required': True}

def prepare_for_xicad_column(objects: list[dict[str, Any]]) -> dict[str, Any]:
    return {'workflow': 'column_basic', 'recommended_alias': 'COL', 'precheck': scan_architecture_layers(objects), 'interactive_required': True}

def prepare_for_xicad_opening(objects: list[dict[str, Any]]) -> dict[str, Any]:
    return {'workflow': 'opening_basic', 'recommended_aliases': ['D1','W1','WO'], 'precheck': scan_architecture_layers(objects), 'interactive_required': True}
