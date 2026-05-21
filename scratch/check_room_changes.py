import win32com.client

try:
    app = win32com.client.GetActiveObject("ZWCAD.Application")
    doc = app.ActiveDocument
    ms = doc.ModelSpace
    
    print("Scanning for '화장실' and '리페어실'...")
    
    for i in range(ms.Count):
        obj = ms.Item(i)
        if "text" in obj.ObjectName.lower():
            text = obj.TextString
            if any(k in text for k in ["화장실", "리페어실", "방음"]):
                print(f"[{obj.Handle}] {text} at {list(obj.InsertionPoint)}")

except Exception as e:
    print(f"Error: {e}")
