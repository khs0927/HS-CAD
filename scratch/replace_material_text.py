import win32com.client

replacements = {
    "석고보드": "방음 판넬",
    "T12.5 석고보드 2PLY": "T25 고밀도 방음 판넬",
    "T9.5 석고보드 2PLY": "T20 고밀도 방음 판넬",
    "경량칸막이": "방음 시스템 칸막이"
}

try:
    app = win32com.client.GetActiveObject("ZWCAD.Application")
    doc = app.ActiveDocument
    ms = doc.ModelSpace
    
    count = 0
    print("Performing replacements...")
    
    for i in range(ms.Count):
        obj = ms.Item(i)
        obj_name = obj.ObjectName.lower()
        
        if "text" in obj_name:
            original = obj.TextString
            modified = original
            
            # Replace longest matches first
            sorted_keys = sorted(replacements.keys(), key=len, reverse=True)
            for key in sorted_keys:
                if key in modified:
                    modified = modified.replace(key, replacements[key])
            
            if original != modified:
                obj.TextString = modified
                print(f"Changed: '{original}' -> '{modified}'")
                count += 1
                
    doc.Regen(1)
    print(f"Successfully updated {count} leader/text objects.")

except Exception as e:
    print(f"Error: {e}")
