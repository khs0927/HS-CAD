import win32com.client
try:
    app = win32com.client.GetActiveObject("ZWCAD.Application")
    doc = app.ActiveDocument
    ms = doc.ModelSpace
    layers = set()
    for i in range(ms.Count):
        layers.add(ms.Item(i).Layer)
    print(f"Layers in model space: {list(layers)}")
    
    h_beam_count = 0
    for i in range(ms.Count):
        if ms.Item(i).Layer.upper() == "COL_H_BEAM":
            h_beam_count += 1
    print(f"H-beams found: {h_beam_count}")
except Exception as e:
    print(f"Error: {e}")
