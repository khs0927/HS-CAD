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
    nx, ny = 0, 0
    if dist > 1e-6:
        nx = (px - closest_x) / dist
        ny = (py - closest_y) / dist
    return dist, (nx, ny)

try:
    app = win32com.client.GetActiveObject("ZWCAD.Application")
    doc = app.ActiveDocument
    ms = doc.ModelSpace
    
    wall_segments = []
    print("Collecting wall segments...")
    count = ms.Count
    for i in range(count):
        try:
            obj = ms.Item(i)
            if obj.Layer.upper() != "WAL": continue
            
            name = obj.ObjectName
            if "Polyline" in name:
                coords = list(obj.Coordinates)
                # Handle both 2D and 3D polylines (2 or 3 doubles per vertex)
                stride = 2 if "LwPolyline" in name or "LightWeightPolyline" in name else 3
                for j in range(0, len(coords) - stride, stride):
                    wall_segments.append(((coords[j], coords[j+1]), (coords[j+stride], coords[j+stride+1])))
                if getattr(obj, "Closed", False):
                    wall_segments.append(((coords[-stride], coords[-stride+1]), (coords[0], coords[1])))
            elif name == "AcDbLine":
                wall_segments.append((list(obj.StartPoint)[:2], list(obj.EndPoint)[:2]))
        except:
            continue

    print(f"Collected {len(wall_segments)} segments.")
    
    beams = []
    for i in range(count):
        try:
            obj = ms.Item(i)
            if obj.Layer == "COL_H_BEAM":
                beams.append(obj)
        except:
            continue
            
    adjusted_count = 0
    min_clearance = 200 # 150 + 50
    
    for beam in beams:
        try:
            coords = list(beam.Coordinates)
            xs = [coords[j] for j in range(0, len(coords), 2)]
            ys = [coords[j+1] for j in range(0, len(coords), 2)]
            cx = sum(xs) / len(xs)
            cy = sum(ys) / len(ys)
            
            total_push_x, total_push_y = 0, 0
            
            for p1, p2 in wall_segments:
                dist, (nx, ny) = get_dist_to_segment(cx, cy, p1[0], p1[1], p2[0], p2[1])
                if dist < min_clearance:
                    push = min_clearance - dist
                    # Only push if it's moving "away" from the wall
                    total_push_x += nx * push
                    total_push_y += ny * push
            
            if abs(total_push_x) > 0.1 or abs(total_push_y) > 0.1:
                beam.Move([0, 0, 0], [total_push_x, total_push_y, 0])
                adjusted_count += 1
        except:
            continue

    doc.Regen(1)
    print(f"Adjusted {adjusted_count} H-beams.")

except Exception as e:
    print(f"Error: {e}")
