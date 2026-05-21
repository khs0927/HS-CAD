import win32com.client
import math

def get_dist_info(px, py, x1, y1, x2, y2):
    dx, dy = x2 - x1, y2 - y1
    if dx == 0 and dy == 0:
        d = math.sqrt((px-x1)**2 + (py-y1)**2)
        return d, (px-x1)/d if d>0 else 0, (py-y1)/d if d>0 else 0
    t = max(0, min(1, ((px - x1) * dx + (py - y1) * dy) / (dx*dx + dy*dy)))
    cx, cy = x1 + t * dx, y1 + t * dy
    d = math.sqrt((px - cx)**2 + (py - cy)**2)
    nx, ny = (px - cx) / d if d > 1e-6 else 0, (py - cy) / d if d > 1e-6 else 0
    return d, nx, ny

try:
    app = win32com.client.GetActiveObject("ZWCAD.Application")
    doc = app.ActiveDocument
    ms = doc.ModelSpace
    
    wall_segments = []
    beams = []
    
    print("Scanning model space...")
    count = ms.Count
    for i in range(count):
        try:
            obj = ms.Item(i)
            layer = obj.Layer.upper()
            if layer == "WAL":
                name = obj.ObjectName
                if "Polyline" in name:
                    coords = list(obj.Coordinates)
                    stride = 2 if "Lw" in name or "Light" in name else 3
                    for j in range(0, len(coords) - stride, stride):
                        wall_segments.append(((coords[j], coords[j+1]), (coords[j+stride], coords[j+stride+1])))
                    if getattr(obj, "Closed", False):
                        wall_segments.append(((coords[-stride], coords[-stride+1]), (coords[0], coords[1])))
                elif name == "AcDbLine":
                    wall_segments.append((list(obj.StartPoint)[:2], list(obj.EndPoint)[:2]))
            elif layer == "COL_H_BEAM":
                beams.append(obj)
        except: continue

    print(f"Found {len(beams)} beams and {len(wall_segments)} wall segments.")
    
    adjusted_count = 0
    min_clearance = 200
    
    for beam in beams:
        try:
            coords = list(beam.Coordinates)
            xs = [coords[j] for j in range(0, len(coords), 2)]
            ys = [coords[j+1] for j in range(0, len(coords), 2)]
            bcx, bcy = sum(xs)/len(xs), sum(ys)/len(ys)
            
            max_v, bx, by = 0, 0, 0
            for p1, p2 in wall_segments:
                d, nx, ny = get_dist_info(bcx, bcy, p1[0], p1[1], p2[0], p2[1])
                if d < min_clearance:
                    v = min_clearance - d
                    if v > max_v:
                        max_v, bx, by = v, nx * v, ny * v
            
            if max_v > 0.1:
                # Use Point3D format for Move
                start = win32com.client.VARIANT(win32com.client.pythoncom.VT_ARRAY | win32com.client.pythoncom.VT_R8, [0, 0, 0])
                end = win32com.client.VARIANT(win32com.client.pythoncom.VT_ARRAY | win32com.client.pythoncom.VT_R8, [bx, by, 0])
                beam.Move(start, end)
                adjusted_count += 1
        except Exception as e:
            print(f"Error moving beam: {e}")

    doc.Regen(1)
    print(f"Successfully adjusted {adjusted_count} H-beams.")

except Exception as e:
    print(f"Error: {e}")
