# -*- coding: utf-8 -*-
import win32com.client
import pythoncom
import time

def draw_leader(ms, start_x, start_y, z, text_lines, direction="right", text_height=150.0):
    try:
        # 기존 도면 스타일에 맞춘 색상 (Cyan = 4)
        layer = "A-ANNO-TEXT"
        doc = ms.Document
        try:
            doc.Layers.Add(layer)
        except:
            pass

        # 방향에 따른 좌표 계산
        if direction == "right":
            pt1 = [start_x, start_y, z]
            pt2 = [start_x + 500, start_y + 500, z]
            pt3 = [start_x + 2000, start_y + 500, z]
            txt_x = start_x + 600
            txt_y_base = start_y + 550
        else:
            pt1 = [start_x, start_y, z]
            pt2 = [start_x - 500, start_y + 500, z]
            pt3 = [start_x - 2000, start_y + 500, z]
            txt_x = start_x - 1900
            txt_y_base = start_y + 550

        # 지시선(Line) 작도
        v_pt1 = win32com.client.VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_R8, pt1)
        v_pt2 = win32com.client.VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_R8, pt2)
        v_pt3 = win32com.client.VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_R8, pt3)
        
        l1 = ms.AddLine(v_pt1, v_pt2)
        l2 = ms.AddLine(v_pt2, v_pt3)
        l1.Layer = layer
        l2.Layer = layer
        l1.Color = 4 # Cyan
        l2.Color = 4 # Cyan

        # 다중 텍스트 기입
        for i, line_text in enumerate(text_lines):
            t_pt = win32com.client.VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_R8, [txt_x, txt_y_base - (i * text_height * 1.5), z])
            txt_obj = ms.AddText(line_text, t_pt, text_height)
            txt_obj.Layer = layer
            txt_obj.Color = 4 # Cyan
            
        return True
    except Exception as e:
        print(f"Error drawing leader: {e}")
        return False

def main():
    print("Connecting to ZWCAD to draft requested section details...")
    try:
        zwcad = win32com.client.Dispatch("ZWCAD.Application")
        doc = zwcad.ActiveDocument
        ms = doc.ModelSpace
        
        # 화면의 중심부근 객체를 찾아 기준점으로 삼음
        base_x, base_y = 0.0, 0.0
        for i in range(ms.Count - 1, max(-1, ms.Count - 500), -1):
            try:
                obj = ms.Item(i)
                if obj.ObjectName == "AcDbPolyline" or obj.ObjectName == "AcDbLine":
                    min_ext, max_ext = obj.GetBoundingBox()
                    base_x = (min_ext[0] + max_ext[0]) / 2.0
                    base_y = (min_ext[1] + max_ext[1]) / 2.0
                    break
            except:
                pass
                
        if base_x == 0.0 and base_y == 0.0:
            print("Warning: Could not find anchor object, using absolute coordinates.")
            base_x, base_y = 10000.0, 10000.0
            
        print(f"Anchor found at X:{base_x:.1f}, Y:{base_y:.1f}")

        # 1. 지붕 단열재 (T180 그라스울 판넬) - 위쪽
        print("Drafting Roof Insulation...")
        draw_leader(ms, base_x, base_y + 3000, 0, ["T180 그라스울 판넬 (지붕단열)"], direction="right")

        # 2. 벽체 단열재 (T100 그라스울 판넬) - 좌측
        print("Drafting Wall Insulation...")
        draw_leader(ms, base_x - 3000, base_y, 0, ["T100 그라스울 판넬 (벽체단열)"], direction="left")

        # 3. 실내재료마감 - 우측 하단
        print("Drafting Indoor Finish...")
        draw_leader(ms, base_x + 2000, base_y - 2000, 0, ["실내재료마감"], direction="right")

        # 4. 철골 H빔 규격 (기둥/보 참고용)
        print("Drafting Steel Beam Spec...")
        draw_leader(ms, base_x + 3000, base_y + 1000, 0, ["H-300x150x6.5x9", "철골 기둥/보 규격"], direction="right")
        
        zwcad.Update()
        print("\nSuccessfully drafted all requested details to ZWCAD!")
        
    except Exception as e:
        print(f"ZWCAD Drafting Failed: {e}")

if __name__ == "__main__":
    main()
