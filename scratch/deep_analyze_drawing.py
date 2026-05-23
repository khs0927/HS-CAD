# -*- coding: utf-8 -*-
import win32com.client
import sys

def deep_analyze_drawing():
    try:
        app = win32com.client.GetActiveObject("ZWCAD.Application")
        doc = app.ActiveDocument
        ms = doc.ModelSpace
    except Exception as e:
        print(f"Error connecting: {e}")
        sys.exit(1)
        
    print(f"Analyzing Document: {doc.Name}")
    
    zium_blocks = []
    hbeam_blocks = []
    leaders = []
    
    # 1. 스캔 수행
    print("\nScanning ModelSpace...")
    for i in range(ms.Count):
        try:
            ent = ms.Item(i)
            name = ent.ObjectName
            
            if name == "AcDbBlockReference":
                bname = ent.Name.upper()
                if "ZIUM" in bname or "SHEET" in bname or "TITLE" in bname:
                    zium_blocks.append({
                        "name": bname,
                        "scale": ent.XScaleFactor,
                        "pos": (ent.InsertionPoint[0], ent.InsertionPoint[1])
                    })
                elif "H-" in bname or "BEAM" in bname or "COL" in bname or "형강" in bname:
                    hbeam_blocks.append({
                        "name": bname,
                        "scale": ent.XScaleFactor,
                        "pos": (ent.InsertionPoint[0], ent.InsertionPoint[1])
                    })
                    
            elif name == "AcDbLeader" or name == "AcDbMLeader":
                leaders.append(name)
        except:
            continue
            
    # 2. 결과 출력
    print("\n--- ZIUM Sheet Blocks Found ---")
    for b in zium_blocks[:5]:
        print(f"Name: {b['name']}, Scale: {b['scale']}, Pos: {b['pos']}")
        
    print(f"\n--- H-Beam/Structure Blocks Found ({len(hbeam_blocks)}) ---")
    for b in hbeam_blocks[:10]:
        print(f"Name: {b['name']}, Scale: {b['scale']}")
        
    print(f"\n--- Leaders Found ---")
    print(f"AcDbLeader: {leaders.count('AcDbLeader')}")
    print(f"AcDbMLeader: {leaders.count('AcDbMLeader')}")

if __name__ == "__main__":
    deep_analyze_drawing()
