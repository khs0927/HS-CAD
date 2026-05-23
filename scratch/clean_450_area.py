# -*- coding: utf-8 -*-
import win32com.client
import sys

def clean_450_area():
    try:
        app = win32com.client.GetActiveObject("ZWCAD.Application")
        doc = app.ActiveDocument
        ms = doc.ModelSpace
    except Exception as e:
        sys.exit(1)
        
    try:
        doc.SendCommand("\x03\x03")
    except:
        pass
        
    delete_count = 0
    for i in range(ms.Count - 1, -1, -1):
        try:
            ent = ms.Item(i)
            x = None
            if hasattr(ent, 'InsertionPoint'):
                x = ent.InsertionPoint[0]
            elif hasattr(ent, 'StartPoint'):
                x = ent.StartPoint[0]
            elif hasattr(ent, 'Coordinates'):
                x = ent.Coordinates[0]
                
            if x is not None and 420000.0 < x < 480000.0:
                ent.Delete()
                delete_count += 1
        except:
            pass
            
    print(f"Cleaned {delete_count} objects around X=450000.")
    doc.Regen(1)

if __name__ == "__main__":
    clean_450_area()
