import win32com.client
import math

def get_dist_to_segment(px, py, x1, y1, x2, y2):
    dx = x2 - x1
    dy = y2 - y1
    if dx == 0 and dy == 0:
        return math.sqrt((px-x1)**2 + (py-y1)**2), (0, 0)
    
    t = ((px - x1) * dx + (py - y1) * dy) / (dx*dx + dy*dy)
    t = max(0, min(1, t))
    
    closest_x = x1 + t * dx
    closest_y = y1 + t * dy
    dist = math.sqrt((px - closest_x)**2 + (py - closest_y)**2)
    
    # Normal vector from wall to point
    nx, ny = 0, 0
    if dist > 0:
        nx = (px - closest_x) / dist
        ny = (py - closest_y) / dist
    
    return dist, (nx, ny)

try:
    app = win32com.client.GetActiveObject("ZWCAD.Application")
    doc = app.ActiveDocument
    ms = doc.ModelSpace
    
    print("Collecting wall segments (WAL)...")
    wall_segments = []
    for i in range(ms.Count):
        obj = ms.Item(i)
        if obj.Layer.upper() == "WAL":
            if obj.ObjectName == "AcDbPolyline" or obj.ObjectName == "AcDbLwPolyline":
                coords = list(obj.Coordinates)
                # AcDbPolyline coordinates are [x1, y1, x2, y2, ...]
                for j in range(0, len(coords) - 2, 2):
                    wall_segments.append(((coords[j], coords[j+1]), (coords[j+2], coords[j+3])))
                if obj.Closed:
                    wall_segments.append(((coords[-2], coords[-1]), (coords[0], coords[1])))
            elif obj.ObjectName == "AcDbLine":
                wall_segments.append((list(obj.StartPoint)[:2], list(obj.EndPoint)[:2]))

    print(f"Collected {len(wall_segments)} wall segments.")
    
    print("Adjusting H-beams (COL_H_BEAM)...")
    beams = []
    for i in range(ms.Count):
        obj = ms.Item(i)
        if obj.Layer == "COL_H_BEAM":
            beams.append(obj)
            
    adjusted_count = 0
    for beam in beams:
        # Get center from polyline vertices
        coords = list(beam.Coordinates)
        xs = [coords[j] for j in range(0, len(coords), 2)]
        ys = [coords[j+1] for j in range(0, len(coords), 2)]
        cx = sum(xs) / len(xs)
        cy = sum(ys) / len(ys)
        
        move_dx, move_dy = 0, 0
        min_clearance = 200 # 150 (half-width) + 50 (gap)
        
        for p1, p2 in wall_segments:
            dist, (nx, ny) = get_dist_to_segment(cx, cy, p1[0], p1[1], p2[0], p2[1])
            if dist < min_clearance:
                push = min_clearance - dist
                move_dx += nx * push
                move_dy += ny * push
        
        if abs(move_dx) > 0.1 or abs(move_dy) > 0.1:
            beam.Move([0, 0, 0], [move_dx, move_dy, 0])
            adjusted_count += 1

    doc.Regen(1)
    print(f"Successfully adjusted {adjusted_count} H-beams to maintain 50mm clearance.")

except Exception as e:
    print(f"Error: {e}")
