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
    
    # Use SelectionSet for faster filtering
    def get_ss(name):
        try: doc.SelectionSets.Item(name).Delete()
        except: pass
        return doc.SelectionSets.Add(name)

    print("Filtering walls (WAL)...")
    ss_wal = get_ss("SS_WAL")
    # Filter for layer WAL
    # Type 8 is Layer, value "WAL"
    import pythoncom
    ss_wal.Select(pythoncom.VT_ARRAY | pythoncom.VT_I2, [8], [pythoncom.VT_ARRAY | pythoncom.VT_VARIANT], ["WAL"])
    
    wall_segments = []
    for i in range(ss_wal.Count):
        obj = ss_wal.Item(i)
        name = obj.ObjectName
        if "Polyline" in name:
            try:
                coords = list(obj.Coordinates)
                stride = 2 if "Lw" in name or "Light" in name else 3
                for j in range(0, len(coords) - stride, stride):
                    wall_segments.append(((coords[j], coords[j+1]), (coords[j+stride], coords[j+stride+1])))
                if getattr(obj, "Closed", False):
                    wall_segments.append(((coords[-stride], coords[-stride+1]), (coords[0], coords[1])))
            except: pass
        elif name == "AcDbLine":
            wall_segments.append((list(obj.StartPoint)[:2], list(obj.EndPoint)[:2]))
    print(f"Collected {len(wall_segments)} wall segments.")

    print("Filtering beams (COL_H_BEAM)...")
    ss_beams = get_ss("SS_BEAMS")
    ss_beams.Select(pythoncom.VT_ARRAY | pythoncom.VT_I2, [8], [pythoncom.VT_ARRAY | pythoncom.VT_VARIANT], ["COL_H_BEAM"])
    
    adjusted_count = 0
    min_clearance = 200
    
    for i in range(ss_beams.Count):
        beam = ss_beams.Item(i)
        try:
            coords = list(beam.Coordinates)
            xs = [coords[j] for j in range(0, len(coords), 2)]
            ys = [coords[j+1] for j in range(0, len(coords), 2)]
            bcx, bcy = sum(xs)/len(xs), sum(ys)/len(ys)
            
            best_push_x, best_push_y, max_v = 0, 0, 0
            for p1, p2 in wall_segments:
                d, nx, ny = get_dist_info(bcx, bcy, p1[0], p1[1], p2[0], p2[1])
                if d < min_clearance:
                    v = min_clearance - d
                    if v > max_v:
                        max_v, best_push_x, best_push_y = v, nx * v, ny * v
            
            if max_v > 0.1:
                beam.Move([0, 0, 0], [best_push_x, best_push_y, 0])
                adjusted_count += 1
        except: continue

    doc.Regen(1)
    print(f"Successfully adjusted {adjusted_count} H-beams using SelectionSets.")

except Exception as e:
    print(f"Error: {e}")
