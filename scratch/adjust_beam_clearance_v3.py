import win32com.client
import math

def get_dist_info(px, py, x1, y1, x2, y2):
    dx = x2 - x1
    dy = y2 - y1
    if dx == 0 and dy == 0:
        d = math.sqrt((px-x1)**2 + (py-y1)**2)
        return d, (px-x1)/d if d>0 else 0, (py-y1)/d if d>0 else 0
    t = ((px - x1) * dx + (py - y1) * dy) / (dx*dx + dy*dy)
    t = max(0, min(1, t))
    cx = x1 + t * dx
    cy = y1 + t * dy
    d = math.sqrt((px - cx)**2 + (py - cy)**2)
    nx, ny = 0, 0
    if d > 1e-6:
        nx = (px - cx) / d
        ny = (py - cy) / d
    return d, nx, ny

try:
    app = win32com.client.GetActiveObject("ZWCAD.Application")
    doc = app.ActiveDocument
    ms = doc.ModelSpace
    
    wall_segments = []
    print("Collecting walls...")
    for i in range(ms.Count):
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

    print(f"Collected {len(wall_segments)} segments.")
    
    beams = []
    for i in range(ms.Count):
        try:
            obj = ms.Item(i)
            if obj.Layer == "COL_H_BEAM":
                beams.append(obj)
        except: continue
            
    adjusted_count = 0
    min_clearance = 200 # 150 (half-width) + 50 (gap)
    
    for beam in beams:
        try:
            coords = list(beam.Coordinates)
            xs = [coords[j] for j in range(0, len(coords), 2)]
            ys = [coords[j+1] for j in range(0, len(coords), 2)]
            bcx, bcy = sum(xs)/len(xs), sum(ys)/len(ys)
            
            # Find the MOST critical push
            # We use a simple approach: check all walls, and for each that violates, 
            # we accumulate the push. To prevent oscillation, we limit to the most significant violation.
            
            best_push_x, best_push_y = 0, 0
            max_violation = 0
            
            for p1, p2 in wall_segments:
                d, nx, ny = get_dist_info(bcx, bcy, p1[0], p1[1], p2[0], p2[1])
                if d < min_clearance:
                    violation = min_clearance - d
                    if violation > max_violation:
                        max_violation = violation
                        best_push_x = nx * violation
                        best_push_y = ny * violation
            
            if max_violation > 0.1:
                beam.Move([0, 0, 0], [best_push_x, best_push_y, 0])
                adjusted_count += 1
        except: continue

    doc.Regen(1)
    print(f"Successfully adjusted {adjusted_count} H-beams.")

except Exception as e:
    print(f"Error: {e}")
