# -*- coding: utf-8 -*-
import win32com.client
import pythoncom
import sys

def find_anchors():
    try:
        app = win32com.client.GetActiveObject("ZWCAD.Application")
        doc = app.ActiveDocument
    except Exception as e:
        print(f"Connection Error: {e}")
        sys.exit(1)
        
    print(f"Connected to ZWCAD: {doc.Name}")
    
    # SelectionSet 생성 및 초기화
    ss_name = "AnchorSearchSS"
    try:
        ss = doc.SelectionSets.Add(ss_name)
    except:
        ss = doc.SelectionSets.Item(ss_name)
        ss.Clear()
        
    # TEXT, MTEXT 필터 정의
    f_type = win32com.client.VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_I2, [0])
    f_data = win32com.client.VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_VARIANT, ["TEXT,MTEXT"])
    
    # 모든 도면 공간에서 텍스트만 필터링하여 선택
    ss.Select(5, None, None, f_type, f_data)
    
    print(f"Filtered text count: {ss.Count}")
    
    found = []
    for i in range(ss.Count):
        try:
            ent = ss.Item(i)
            txt = ent.TextString
            # 한글 검색어 매칭
            if any(k in txt for k in ["종단면도", "횡단면도", "단면도", "A301", "지붕단열", "벽체단열"]):
                found.append({
                    "text": txt,
                    "x": ent.InsertionPoint[0],
                    "y": ent.InsertionPoint[1],
                    "layer": ent.Layer,
                    "object_name": ent.ObjectName
                })
        except Exception:
            continue
            
    print("\n--- FOUND ANCHORS ---")
    for f in found:
        print(f"[{f['layer']}] {f['object_name']} at ({f['x']:.2f}, {f['y']:.2f}) -> {repr(f['text'])}")
        
    ss.Clear()
    ss.Delete()

if __name__ == "__main__":
    find_anchors()
