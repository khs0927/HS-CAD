from __future__ import annotations

from typing import Any
from shapely.geometry import LineString, Polygon, MultiLineString
from shapely.ops import polygonize, unary_union

def polygonize_full(entities: list[dict[str, Any]]) -> list[Polygon]:
    """Perform robust polygonization on raw CAD linear entities (LINE, POLYLINE, ARC, CIRCLE).
    
    Uses shapely.ops.polygonize to extract all topologically valid closed loops.
    """
    lines: list[LineString] = []
    
    for ent in entities:
        ent_type = str(ent.get('entity_type') or '').upper()
        
        if ent_type == 'LINE':
            start = ent.get('start')
            end = ent.get('end')
            if start and end and len(start) >= 2 and len(end) >= 2:
                lines.append(LineString([start[:2], end[:2]]))
                
        elif ent_type == 'POLYLINE':
            pts = ent.get('points')
            if pts and len(pts) >= 2:
                lines.append(LineString([p[:2] for p in pts]))
                
        elif ent_type == 'CIRCLE':
            # Approximate circle with segments
            center = ent.get('center')
            radius = ent.get('radius')
            if center is not None and radius is not None and len(center) >= 2:
                import math
                cx, cy = center[0], center[1]
                steps = 64
                circle_pts = []
                for i in range(steps):
                    theta = 2.0 * math.pi * i / steps
                    circle_pts.append((cx + radius * math.cos(theta), cy + radius * math.sin(theta)))
                circle_pts.append(circle_pts[0])  # Force close perfectly without float precision noise
                lines.append(LineString(circle_pts))
                
        elif ent_type == 'ARC':
            center = ent.get('center')
            radius = ent.get('radius')
            start_ang = ent.get('start_angle')
            end_ang = ent.get('end_angle')
            if center is not None and radius is not None and start_ang is not None and end_ang is not None and len(center) >= 2:
                import math
                cx, cy = center[0], center[1]
                s_rad = math.radians(start_ang)
                e_rad = math.radians(end_ang)
                if e_rad < s_rad:
                    e_rad += 2.0 * math.pi
                steps = 32
                arc_pts = []
                for i in range(steps + 1):
                    t = s_rad + (e_rad - s_rad) * i / steps
                    arc_pts.append((cx + radius * math.cos(t), cy + radius * math.sin(t)))
                lines.append(LineString(arc_pts))

    if not lines:
        return []

    polygons: list[Polygon] = []
    remaining_lines: list[LineString] = []
    
    for line in lines:
        # If it is already a closed ring (using tiny threshold for robust float comparison)
        p_start = line.coords[0]
        p_end = line.coords[-1]
        dist = ((p_start[0] - p_end[0])**2 + (p_start[1] - p_end[1])**2)**0.5
        if len(line.coords) >= 4 and dist < 1e-4:
            try:
                # Force closing coords
                coords = list(line.coords)
                coords[-1] = coords[0]
                polygons.append(Polygon(coords))
            except Exception:
                remaining_lines.append(line)
        else:
            remaining_lines.append(line)

    if remaining_lines:
        # Flatten and union overlapping/touching line structures for stable topology
        try:
            merged = unary_union(remaining_lines)
            polygons.extend(list(polygonize(merged)))
        except Exception:
            # Fallback to direct polygonize without union
            polygons.extend(list(polygonize(remaining_lines)))
            
    return polygons
