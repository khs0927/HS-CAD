# -*- coding: utf-8 -*-
import win32com.client
import pythoncom
import sys

def fast_analyze_blocks():
    try:
        app = win32com.client.GetActiveObject("ZWCAD.Application")
        doc = app.ActiveDocument
    except:
        sys.exit(1)
        
    print("--- 1. Scanning Inserted Block References ---")
    ss_name = "BlockScannerSS"
    try:
        ss = doc.SelectionSets.Add(ss_name)
    except:
        ss = doc.SelectionSets.Item(ss_name)
        ss.Clear()
        
    # Filter for BlockReferences
    f_type = win32com.client.VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_I2, [0])
    f_data = win32com.client.VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_VARIANT, ["INSERT"])
    
    ss.Select(5, None, None, f_type, f_data)
    
    zium_blocks = []
    hbeam_blocks = []
    
    for i in range(ss.Count):
        try:
            ent = ss.Item(i)
            bname = ent.Name.upper()
            if "ZIUM" in bname or "SHEET" in bname:
                zium_blocks.append({
                    "name": bname,
                    "scale": ent.XScaleFactor,
                    "pos": (ent.InsertionPoint[0], ent.InsertionPoint[1])
                })
            elif "H-" in bname or "BEAM" in bname or "COL" in bname or "형강" in bname or "H " in bname:
                hbeam_blocks.append({
                    "name": bname,
                    "scale": ent.XScaleFactor,
                    "pos": (ent.InsertionPoint[0], ent.InsertionPoint[1])
                })
        except:
            continue
            
    print(f"\n--- ZIUM Sheet Blocks Found ({len(zium_blocks)}) ---")
    for b in zium_blocks[:5]:
        print(f"Name: {b['name']}, Scale: {b['scale']}, Pos: {b['pos']}")
        
    print(f"\n--- H-Beam/Structure Blocks Found ({len(hbeam_blocks)}) ---")
    for b in hbeam_blocks[:10]:
        print(f"Name: {b['name']}, Scale: {b['scale']}")
        
    ss.Clear()
    ss.Delete()

if __name__ == "__main__":
    fast_analyze_blocks()
