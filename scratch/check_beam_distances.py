import win32com.client
import math

def get_dist_to_segment(px, py, x1, y1, x2, y2):
    dx = x2 - x1
    dy = y2 - y1
    if dx == 0 and dy == 0:
        return math.sqrt((px-x1)**2 + (py-y1)**2)
    t = ((px - x1) * dx + (py - y1) * dy) / (dx*dx + dy*dy)
    t = max(0, min(1, t))
    closest_x = x1 + t * dx
    closest_y = y1 + t * dy
    return math.sqrt((px - closest_x)**2 + (py - closest_y)**2)

try:
    app = win32com.client.GetActiveObject("ZWCAD.Application")
    doc = app.ActiveDocument
    ms = doc.ModelSpace
    
    wall_segments = []
    count = ms.Count
    for i in range(count):
        try:
            obj = ms.Item(i)
            if obj.Layer.upper() != "WAL": continue
            name = obj.ObjectName
            if "Polyline" in name:
                coords = list(obj.Coordinates)
                stride = 2 if "LwPolyline" in name or "LightWeightPolyline" in name else 3
                for j in range(0, len(coords) - stride, stride):
                    wall_segments.append(((coords[j], coords[j+1]), (coords[j+stride], coords[j+stride+1])))
                if getattr(obj, "Closed", False):
                    wall_segments.append(((coords[-stride], coords[-stride+1]), (coords[0], coords[1])))
            elif name == "AcDbLine":
                wall_segments.append((list(obj.StartPoint)[:2], list(obj.EndPoint)[:2]))
        except: continue

    beams = []
    for i in range(count):
        try:
            obj = ms.Item(i)
            if obj.Layer == "COL_H_BEAM":
                beams.append(obj)
        except: continue
            
    print(f"Checking {len(beams)} beams against {len(wall_segments)} segments...")
    
    for beam in beams[:20]: # Check first 20
        coords = list(beam.Coordinates)
        xs = [coords[j] for j in range(0, len(coords), 2)]
        ys = [coords[j+1] for j in range(0, len(coords), 2)]
        cx, cy = sum(xs)/len(xs), sum(ys)/len(ys)
        
        min_d = float('inf')
        for p1, p2 in wall_segments:
            d = get_dist_to_segment(cx, cy, p1[0], p1[1], p2[0], p2[1])
            if d < min_d: min_d = d
        
        print(f"Beam at ({cx:.1f}, {cy:.1f}) min distance to wall: {min_d:.1f}")

except Exception as e:
    print(f"Error: {e}")
