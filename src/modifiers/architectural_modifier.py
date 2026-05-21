from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any, Iterable
import yaml
from pathlib import Path

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

def _load_rules_from_engine(engine: Any) -> Any:
    if hasattr(engine, "load_all"):
        return engine.load_all()
    if hasattr(engine, "load_all_rules"):
        engine.load_all_rules()
        return engine
    return engine

def _first_number(values: list[float], default: float) -> float:
    try:
        return float(values[0])
    except Exception:
        return default

def _match_text(value: str, candidates: Iterable[str]) -> bool:
    needle = value.lower()
    return any(needle in str(candidate).lower() for candidate in candidates)

def create_xicad_wall_actions(
    engine: Any,
    group_name: str,
    length: float,
    direction: str = "horizontal",
    origin: tuple[float, float, float] = (0, 0, 0),
) -> list[dict[str, Any]]:
    rules = _load_rules_from_engine(engine)
    styles = list(getattr(rules, "wall_styles", []) or [])
    style = next(
        (
            item for item in styles
            if _match_text(group_name, [getattr(item, "name", ""), getattr(item, "raw", "")])
        ),
        None,
    )
    offsets = list(getattr(style, "offsets", []) or []) if style else []
    if len(offsets) < 2:
        thickness = float(getattr(style, "total_thickness", 200.0) or 200.0) if style else 200.0
        offsets = [-thickness / 2.0, thickness / 2.0]

    x0, y0, z = _origin3(origin)
    horizontal = direction.lower().startswith("h")
    actions: list[dict[str, Any]] = []
    for index, offset in enumerate(sorted(float(v) for v in offsets)):
        points = (
            [[x0, y0 + offset, z], [x0 + length, y0 + offset, z]]
            if horizontal else
            [[x0 + offset, y0, z], [x0 + offset, y0 + length, z]]
        )
        actions.append({
            "action": "create_polyline",
            "layer": "A-WALL",
            "closed": False,
            "points": points,
            "name": f"WallLine_{index}",
            "source": "xicad_rule_engine",
        })
    return actions

def _find_steel_spec(engine: Any, is_xicad: bool, steel_type: str, spec_name: str) -> Any | None:
    rules = _load_rules_from_engine(engine)
    specs = list(getattr(rules, "steel_specs", []) or [])
    for spec in specs:
        category = str(getattr(spec, "category", ""))
        name = str(getattr(spec, "name", ""))
        raw = str(getattr(spec, "raw", ""))
        if _match_text(steel_type, [category, raw]) and _match_text(spec_name, [name, raw]):
            return spec
    for spec in specs:
        name = str(getattr(spec, "name", ""))
        raw = str(getattr(spec, "raw", ""))
        if _match_text(spec_name, [name, raw]):
            return spec
    return None

def create_steel_beam_actions(
    engine: Any,
    is_xicad: bool,
    steel_type: str,
    spec_name: str,
    origin: tuple[float, float, float] = (0, 0, 0),
) -> list[dict[str, Any]]:
    spec = _find_steel_spec(engine, is_xicad, steel_type, spec_name)
    values = list(getattr(spec, "values", []) or []) if spec else []
    height = _first_number(values, 200.0)
    width = float(values[1]) if len(values) > 1 else height
    web_thickness = float(values[2]) if len(values) > 2 else 8.0
    flange_thickness = float(values[3]) if len(values) > 3 else 12.0

    x, y, z = _origin3(origin)
    if "h" in steel_type.lower() or len(values) >= 4:
        tw = min(web_thickness, width)
        tf = min(flange_thickness, height / 2.0)
        points = [
            [x - width / 2, y + height / 2, z],
            [x + width / 2, y + height / 2, z],
            [x + width / 2, y + height / 2 - tf, z],
            [x + tw / 2, y + height / 2 - tf, z],
            [x + tw / 2, y - height / 2 + tf, z],
            [x + width / 2, y - height / 2 + tf, z],
            [x + width / 2, y - height / 2, z],
            [x - width / 2, y - height / 2, z],
            [x - width / 2, y - height / 2 + tf, z],
            [x - tw / 2, y - height / 2 + tf, z],
            [x - tw / 2, y + height / 2 - tf, z],
            [x - width / 2, y + height / 2 - tf, z],
            [x - width / 2, y + height / 2, z],
        ]
        name = f"H_Beam_{spec_name}"
    else:
        points = [
            [x - width / 2, y + height / 2, z],
            [x + width / 2, y + height / 2, z],
            [x + width / 2, y - height / 2, z],
            [x - width / 2, y - height / 2, z],
            [x - width / 2, y + height / 2, z],
        ]
        name = f"Box_Beam_{spec_name}"

    return [{
        "action": "create_polyline",
        "layer": "A-BEAM-STEEL",
        "closed": True,
        "points": points,
        "name": name,
        "source": "xicad_rule_engine" if is_xicad else "archioffice_rule_engine",
    }]

def insert_spec_block_actions(
    engine: Any,
    is_xicad: bool,
    category: str,
    block_name: str,
    origin: tuple[float, float, float] = (0, 0, 0),
) -> list[dict[str, Any]]:
    rules = _load_rules_from_engine(engine)
    layer = f"A-AO-SYM-{category.upper()}" if not is_xicad else "A-XICAD-SYM"
    if is_xicad:
        for rule in list(getattr(rules, "block_layer_rules", []) or []):
            pattern = str(getattr(rule, "pattern", ""))
            if pattern and _match_text(category, [pattern]):
                layer = f"A-SYM-{getattr(rule, 'layer', 'SYM')}"
                break
    x, y, z = _origin3(origin)
    return [{
        "action": "insert_block",
        "block_name": block_name,
        "layer": layer,
        "insert": [x, y, z],
        "rotation": 0,
        "scale": [1.0, 1.0, 1.0],
        "source": "xicad_rule_engine" if is_xicad else "archioffice_rule_engine",
    }]

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
