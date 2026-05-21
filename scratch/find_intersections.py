import win32com.client
import math

def get_intersections(lines):
    intersections = []
    for i in range(len(lines)):
        for j in range(i + 1, len(lines)):
            l1 = lines[i]
            l2 = lines[j]
            
            # Simple line-line intersection (ignoring Z)
            x1, y1 = l1['start'][0], l1['start'][1]
            x2, y2 = l1['end'][0], l1['end'][1]
            x3, y3 = l2['start'][0], l2['start'][1]
            x4, y4 = l2['end'][0], l2['end'][1]
            
            denom = (y4 - y3) * (x2 - x1) - (x4 - x3) * (y2 - y1)
            if denom == 0: continue # Parallel
            
            ua = ((x4 - x3) * (y1 - y3) - (y4 - y3) * (x1 - x3)) / denom
            ub = ((x2 - x1) * (y1 - y3) - (y2 - y1) * (x1 - x3)) / denom
            
            # Check if intersection is within line segments
            if 0 <= ua <= 1 and 0 <= ub <= 1:
                x = x1 + ua * (x2 - x1)
                y = y1 + ua * (y2 - y1)
                intersections.append((x, y))
    return intersections

try:
    app = win32com.client.GetActiveObject("ZWCAD.Application")
    doc = app.ActiveDocument
    ms = doc.ModelSpace
    
    cen_lines = []
    print("Collecting lines on CEN layer...")
    for i in range(ms.Count):
        obj = ms.Item(i)
        if obj.ObjectName == "AcDbLine" and obj.Layer == "CEN":
            cen_lines.append({
                'start': list(obj.StartPoint),
                'end': list(obj.EndPoint)
            })
    
    print(f"Found {len(cen_lines)} lines on CEN layer.")
    intersections = get_intersections(cen_lines)
    print(f"Found {len(intersections)} intersections.")
    for idx, (x, y) in enumerate(intersections):
        print(f"Intersection {idx}: ({x:.2f}, {y:.2f})")

except Exception as e:
    print(f"Error: {e}")
