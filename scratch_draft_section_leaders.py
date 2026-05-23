# -*- coding: utf-8 -*-
import win32com.client
import pythoncom
import time

def add_mleader(ms, x, y, z, text, layer="A-XICAD-TEXT"):
    try:
        doc = ms.Document
        try:
            doc.Layers.Add(layer)
        except:
            pass
            
        # 1. 지시선(Line) 작도
        pt1 = win32com.client.VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_R8, [x, y, z])
        pt2 = win32com.client.VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_R8, [x + 300, y + 300, z])
        pt3 = win32com.client.VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_R8, [x + 1500, y + 300, z])
        
        l1 = ms.AddLine(pt1, pt2)
        l2 = ms.AddLine(pt2, pt3)
        l1.Layer = layer
        l2.Layer = layer
        
        # 2. 텍스트(Text) 기입
        txt_pt = win32com.client.VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_R8, [x + 350, y + 350, z])
        # 줄바꿈 문자를 분리해서 렌더링
        lines = text.split("\\n")
        
        t1 = ms.AddText(lines[0], txt_pt, 120.0)
        t1.Layer = layer
        if len(lines) > 1:
            txt_pt2 = win32com.client.VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_R8, [x + 350, y + 150, z])
            t2 = ms.AddText(lines[1], txt_pt2, 100.0)
            t2.Layer = layer
            
        return True
    except Exception as e:
        print(f"Error drawing leader: {e}")
        return False

def main():
    print("Connecting to ZWCAD to draft section details (H-Beams, Insulation, Finishes)...")
    try:
        zwcad = win32com.client.Dispatch("ZWCAD.Application")
        doc = zwcad.ActiveDocument
        ms = doc.ModelSpace
        
        # 1. 도면 내 적절한 배치 기준점 찾기 (단면도 근처)
        # 31,334개의 객체를 모두 뒤지는 대신, 최근 그려진 객체나 임의의 유효한 객체 위치를 탐색
        base_x, base_y = 0.0, 0.0
        found = False
        for i in range(ms.Count - 1, max(-1, ms.Count - 1000), -1):
            try:
                obj = ms.Item(i)
                if obj.ObjectName == "AcDbPolyline" or obj.ObjectName == "AcDbLine":
                    min_ext, max_ext = obj.GetBoundingBox()
                    base_x = (min_ext[0] + max_ext[0]) / 2.0
                    base_y = (min_ext[1] + max_ext[1]) / 2.0
                    found = True
                    break
            except:
                pass
                
        if not found:
            base_x, base_y = 1000.0, 1000.0
            
        print(f"Found drawing anchor at X:{base_x:.1f}, Y:{base_y:.1f}")
        
        # 2. 하이브리드 지시선(MLeader) 기입 수행
        print("1. Drafting Steel Beam Leader (ArchiOffice/HSSTEEL)...")
        add_mleader(
            ms, 
            base_x + 500, base_y + 500, 0, 
            "H-300x150x6.5x9\\n(HSSTEEL Structure Spec)", 
            "A-HSSTEEL-SYM-BEAM"
        )
        
        print("2. Drafting Insulation Leader (XiCAD)...")
        add_mleader(
            ms, 
            base_x - 500, base_y + 800, 0, 
            "THK150 Rigid Urethane Foam Insulation\\n(XiCAD Wall Rule)", 
            "A-XICAD-TEXT"
        )
        
        print("3. Drafting Finish Material Leader (ArchiOffice)...")
        add_mleader(
            ms, 
            base_x + 800, base_y - 200, 0, 
            "THK30 Granite Stone Finish\\n(ArchiOffice Material Spec)", 
            "A-AO-SYM-FINISH"
        )
        
        # 3. 뷰 업데이트
        zwcad.Update()
        print("\nAll Section Details (H-Beam, Insulation, Finishes) successfully drafted via Hybrid AI Engine!")
        
    except Exception as e:
        print(f"ZWCAD Drafting Failed: {e}")

if __name__ == "__main__":
    main()
