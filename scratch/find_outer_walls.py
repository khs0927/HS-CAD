import win32com.client

try:
    app = win32com.client.GetActiveObject("ZWCAD.Application")
    doc = app.ActiveDocument
    ms = doc.ModelSpace
    
    print("Searching for potential outer wall objects (WAL, BOUND, AREA)...")
    
    potential_walls = []
    
    for i in range(ms.Count):
        obj = ms.Item(i)
        layer = obj.Layer.upper()
        if layer in ["WAL", "BOUND", "AREA"]:
            if obj.ObjectName in ["AcDbPolyline", "AcDbLine", "AcDbLwPolyline"]:
                potential_walls.append({'layer': layer, 'type': obj.ObjectName, 'handle': obj.Handle})

    print(f"Found {len(potential_walls)} potential wall objects.")
    # Show first 10 for reference
    for item in potential_walls[:10]:
        print(f"[{item['handle']}] {item['layer']} {item['type']}")

except Exception as e:
    print(f"Error: {e}")
