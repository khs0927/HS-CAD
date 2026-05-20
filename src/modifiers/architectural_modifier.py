from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any, Iterable

ARCH_LAYERS = {
    'A-WALL', 'A-COLUMN', 'A-BEAM', 'A-SLAB', 'A-DOOR', 'A-WINDOW',
    'A-ROOM', 'A-TEXT', 'A-DIMS', 'A-GRID', 'A-BOUNDARY', 'A-XICAD'
}

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

def _rectangle_points(cx: float, cy: float, z: float, width: float, depth: float) -> list[list[float]]:
    hw = width / 2
    hd = depth / 2
    return [[cx - hw, cy - hd, z], [cx + hw, cy - hd, z], [cx + hw, cy + hd, z], [cx - hw, cy + hd, z]]


def place_columns(
    block_name: str | None,
    width: float,
    depth: float,
    grid_x: float,
    grid_y: float,
    origin: tuple[float,float,float]=(0,0,0),
    layer: str='A-COLUMN',
    column_width: float = 500,
    column_depth: float = 500,
    placeholder: bool = True,
) -> list[dict[str, Any]]:
    x0, y0, z = _origin3(origin)
    actions: list[dict[str, Any]] = []
    x = 0.0
    while x <= width + 1e-6:
        y = 0.0
        while y <= depth + 1e-6:
            insert = [x0+x, y0+y, z]
            fallback = {'action':'create_rectangle_placeholder','layer':layer,'points':_rectangle_points(insert[0], insert[1], z, column_width, column_depth)}
            if block_name:
                actions.append({'action':'insert_block','block_name':block_name,'layer':layer,'insert':insert,'rotation':0,'scale':[1,1,1], 'fallback': fallback if placeholder else None})
            else:
                actions.append(fallback if placeholder else {'action':'create_circle_placeholder','layer':layer,'center':insert,'radius':max(column_width, column_depth) / 2})
            y += grid_y
        x += grid_x
    return actions

def place_beams_2d(width: float, depth: float, grid_x: float, grid_y: float, origin: tuple[float,float,float]=(0,0,0), layer: str='A-BEAM', beam_width: float | None = None) -> list[dict[str, Any]]:
    x0, y0, z = _origin3(origin)
    actions: list[dict[str, Any]] = []
    x = 0.0
    while x <= width + 1e-6:
        if beam_width:
            half = beam_width / 2
            actions.append({'action':'create_polyline','layer':layer,'closed':True,'name':f'BX{x:g}','points':[[x0+x-half,y0,z],[x0+x+half,y0,z],[x0+x+half,y0+depth,z],[x0+x-half,y0+depth,z]]})
        else:
            actions.append({'action':'create_line','layer':layer,'name':f'BX{x:g}','start':[x0+x,y0,z],'end':[x0+x,y0+depth,z]})
        x += grid_x
    y = 0.0
    while y <= depth + 1e-6:
        if beam_width:
            half = beam_width / 2
            actions.append({'action':'create_polyline','layer':layer,'closed':True,'name':f'BY{y:g}','points':[[x0,y0+y-half,z],[x0+width,y0+y-half,z],[x0+width,y0+y+half,z],[x0,y0+y+half,z]]})
        else:
            actions.append({'action':'create_line','layer':layer,'name':f'BY{y:g}','start':[x0,y0+y,z],'end':[x0+width,y0+y,z]})
        y += grid_y
    return actions

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
    keywords = ('ROOM', 'AREA', '실', '면적', 'A-ROOM')
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
