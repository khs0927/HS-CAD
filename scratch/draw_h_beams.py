import win32com.client
import math

def get_intersections(lines):
    intersections = []
    for i in range(len(lines)):
        for j in range(i + 1, len(lines)):
            l1 = lines[i]
            l2 = lines[j]
            x1, y1 = l1['start'][0], l1['start'][1]
            x2, y2 = l1['end'][0], l1['end'][1]
            x3, y3 = l2['start'][0], l2['start'][1]
            x4, y4 = l2['end'][0], l2['end'][1]
            denom = (y4 - y3) * (x2 - x1) - (x4 - x3) * (y2 - y1)
            if denom == 0: continue
            ua = ((x4 - x3) * (y1 - y3) - (y4 - y3) * (x1 - x3)) / denom
            ub = ((x2 - x1) * (y1 - y3) - (y2 - y1) * (x1 - x3)) / denom
            if 0 <= ua <= 1 and 0 <= ub <= 1:
                x = x1 + ua * (x2 - x1)
                y = y1 + ua * (y2 - y1)
                intersections.append((x, y))
    return intersections

def draw_h_beam(ms, cx, cy, layer_name):
    # H-300x300 (simplified)
    # H=300, B=300, t1=15, t2=10
    half_h = 150
    half_b = 150
    t1 = 15
    half_t2 = 5
    
    pts = [
        cx - half_b, cy + half_h,
        cx + half_b, cy + half_h,
        cx + half_b, cy + half_h - t1,
        cx + half_t2, cy + half_h - t1,
        cx + half_t2, cy - half_h + t1,
        cx + half_b, cy - half_h + t1,
        cx + half_b, cy - half_h,
        cx - half_b, cy - half_h,
        cx - half_b, cy - half_h + t1,
        cx - half_t2, cy - half_h + t1,
        cx - half_t2, cy + half_h - t1,
        cx - half_b, cy + half_h - t1,
        cx - half_b, cy + half_h # Close
    ]
    
    # ZWCAD AddLightWeightPolyline takes a flat list of doubles (X, Y)
    poly = ms.AddLightWeightPolyline(pts)
    poly.Layer = layer_name
    poly.Closed = True
    return poly

try:
    app = win32com.client.GetActiveObject("ZWCAD.Application")
    doc = app.ActiveDocument
    ms = doc.ModelSpace
    
    # Ensure layer exists
    layer_name = "COL_H_BEAM"
    try:
        doc.Layers.Add(layer_name)
    except:
        pass
    
    cen_lines = []
    for i in range(ms.Count):
        obj = ms.Item(i)
        if obj.ObjectName == "AcDbLine" and obj.Layer == "CEN":
            cen_lines.append({
                'start': list(obj.StartPoint),
                'end': list(obj.EndPoint)
            })
    
    intersections = get_intersections(cen_lines)
    print(f"Drawing {len(intersections)} H-beams...")
    
    for x, y in intersections:
        draw_h_beam(ms, x, y, layer_name)
    
    doc.Regen(1)
    print("Done.")

except Exception as e:
    print(f"Error: {e}")
