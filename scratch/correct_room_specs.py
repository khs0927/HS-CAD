import win32com.client

try:
    app = win32com.client.GetActiveObject("ZWCAD.Application")
    doc = app.ActiveDocument
    ms = doc.ModelSpace
    
    print("Correcting Restroom and Repair Room specs...")
    
    # Restroom (화장실) - near handle 818
    # Repair Room (리페어실) - near handle 824
    
    # Based on the previous scan:
    # [818] T100 방음 시스템 칸막이 (T9.5 방음 판넬 2P)
    # [824] T20 고밀도 방음 판넬
    
    targets = {
        "818": "T100 경량칸막이 (T9.5 방수석고보드 2P)",
        "824": "T12.5 일반석고보드 2PLY"
    }
    
    count = 0
    for handle, new_text in targets.items():
        try:
            obj = doc.HandleToObject(handle)
            old_text = obj.TextString
            obj.TextString = new_text
            print(f"Updated [{handle}]: '{old_text}' -> '{new_text}'")
            count += 1
        except Exception as e:
            print(f"Error updating handle {handle}: {e}")
            
    doc.Regen(1)
    print(f"Correction complete. {count} objects updated.")

except Exception as e:
    print(f"Error: {e}")
