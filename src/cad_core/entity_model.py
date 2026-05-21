from __future__ import annotations
from typing import Any, Literal
from pydantic import BaseModel, Field

class BaseCADEntity(BaseModel):
    handle: str | None = None
    object_name: str = ''
    entity_type: str = 'UNKNOWN'
    layer: str | None = None
    color: str | int | None = None
    raw: dict[str, Any] = Field(default_factory=dict)

class LineEntity(BaseCADEntity):
    entity_type: Literal['LINE'] = 'LINE'
    start: list[float] = Field(default_factory=list)
    end: list[float] = Field(default_factory=list)

class PolylineEntity(BaseCADEntity):
    entity_type: Literal['POLYLINE'] = 'POLYLINE'
    points: list[list[float]] = Field(default_factory=list)
    closed: bool | None = None

class TextEntity(BaseCADEntity):
    entity_type: Literal['TEXT'] = 'TEXT'
    insert: list[float] | None = None
    text: str | None = None
    rotation: float | None = None

class BlockEntity(BaseCADEntity):
    entity_type: Literal['BLOCK'] = 'BLOCK'
    name: str | None = None
    effective_name: str | None = None
    insert: list[float] | None = None
    rotation: float | None = None
    x_scale: float | None = None
    y_scale: float | None = None
    z_scale: float | None = None

class CircleEntity(BaseCADEntity):
    entity_type: Literal['CIRCLE'] = 'CIRCLE'
    center: list[float] | None = None
    radius: float | None = None

class UnknownEntity(BaseCADEntity):
    entity_type: Literal['UNKNOWN'] = 'UNKNOWN'

def entity_from_raw(raw: dict[str, Any]) -> BaseCADEntity:
    object_name = str(raw.get('object_name') or raw.get('ObjectName') or '')
    low = object_name.lower()
    common = {
        'handle': raw.get('handle') or raw.get('Handle'),
        'object_name': object_name,
        'layer': raw.get('layer') or raw.get('Layer'),
        'color': raw.get('color') or raw.get('Color'),
        'raw': raw,
    }
    if 'line' in low and 'poly' not in low:
        return LineEntity(**common, start=raw.get('start') or [], end=raw.get('end') or [])
    if 'polyline' in low or 'lwpolyline' in low:
        return PolylineEntity(**common, points=raw.get('points') or [], closed=raw.get('closed'))
    if 'text' in low:
        return TextEntity(**common, insert=raw.get('insert'), text=raw.get('text'), rotation=raw.get('rotation'))
    if 'block' in low or 'insert' in low:
        return BlockEntity(
            **common,
            name=raw.get('name') or raw.get('Name'),
            effective_name=raw.get('effective_name') or raw.get('EffectiveName'),
            insert=raw.get('insert') or raw.get('InsertionPoint'),
            rotation=raw.get('rotation') or raw.get('Rotation'),
            x_scale=raw.get('x_scale') or raw.get('XScaleFactor'),
            y_scale=raw.get('y_scale') or raw.get('YScaleFactor'),
            z_scale=raw.get('z_scale') or raw.get('ZScaleFactor'),
        )
    if 'circle' in low:
        return CircleEntity(**common, center=raw.get('center'), radius=raw.get('radius'))
    return UnknownEntity(**common)
