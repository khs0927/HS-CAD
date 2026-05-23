# -*- coding: utf-8 -*-
import win32com.client
import sys

def analyze_existing_drawing():
    try:
        app = win32com.client.GetActiveObject("ZWCAD.Application")
        doc = app.ActiveDocument
        ms = doc.ModelSpace
    except:
        sys.exit(1)
        
    print("--- 1. Analyzing ZIUM Sheet Blocks ---")
    count = 0
    for i in range(ms.Count):
        try:
            ent = ms.Item(i)
            if ent.ObjectName == "AcDbBlockReference":
                if "ZIUM" in ent.Name.upper() or "SHEET" in ent.Name.upper():
                    print(f"Block: {ent.Name}, Scale X/Y/Z: {ent.XScaleFactor} / {ent.YScaleFactor} / {ent.ZScaleFactor}")
                    count += 1
                    if count >= 3:
                        break
        except:
            pass
            
    print("--- 2. Analyzing Existing Leaders ---")
    leader_count = 0
    mleader_count = 0
    for i in range(ms.Count):
        try:
            ent = ms.Item(i)
            if ent.ObjectName == "AcDbLeader":
                leader_count += 1
            elif ent.ObjectName == "AcDbMLeader":
                mleader_count += 1
        except:
            pass
            
    print(f"AcDbLeader Count: {leader_count}")
    print(f"AcDbMLeader Count: {mleader_count}")

if __name__ == "__main__":
    analyze_existing_drawing()
