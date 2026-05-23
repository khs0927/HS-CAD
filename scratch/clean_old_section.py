# -*- coding: utf-8 -*-
import win32com.client
import sys

def clean_old_section():
    try:
        app = win32com.client.GetActiveObject("ZWCAD.Application")
        doc = app.ActiveDocument
        ms = doc.ModelSpace
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)
        
    delete_count = 0
    # 삭제 대상: X 좌표가 320000 ~ 400000 사이인 객체들
    for i in range(ms.Count - 1, -1, -1):
        try:
            ent = ms.Item(i)
            # 대략적인 바운딩 박스를 구할 수 없으므로 StartPoint나 InsertionPoint 활용
            x = None
            if hasattr(ent, 'StartPoint'):
                x = ent.StartPoint[0]
            elif hasattr(ent, 'InsertionPoint'):
                x = ent.InsertionPoint[0]
            elif hasattr(ent, 'Coordinates'):
                x = ent.Coordinates[0]
                
            if x is not None and 320000.0 < x < 400000.0:
                ent.Delete()
                delete_count += 1
        except:
            pass
            
    print(f"Cleaned {delete_count} objects in the section area.")
    doc.Regen(1)

if __name__ == "__main__":
    clean_old_section()
