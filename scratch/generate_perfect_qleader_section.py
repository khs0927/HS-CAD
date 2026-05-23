# -*- coding: utf-8 -*-
import win32com.client
import pythoncom
import sys
import math
import os

def generate_perfect_qleader_section():
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
        
    base_x = 450000.0
    base_y = 200000.0
    height = 10000.0
    span = 10000.0
    half_span = span / 2.0
    slope = 0.1
    ridge_y = base_y + height + (half_span * slope)
    
    layers = {
        "COL": 2, "WALL1": 2, "중심선": 1, "치수": 7, "글씨": 3
    }
    for l_name, color in layers.items():
        try:
            doc.Layers.Add(l_name).Color = color
        except:
            pass
            
    # Set DimStyle
    try:
        for i in range(doc.DimStyles.Count):
            ds = doc.DimStyles.Item(i)
            if "300DIM" in ds.Name or "100DIM" in ds.Name:
                doc.ActiveDimStyle = ds
                break
    except:
        pass

    def draw_line(sp, ep, layer):
        v_sp = win32com.client.VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_R8, sp)
        v_ep = win32com.client.VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_R8, ep)
        line = ms.AddLine(v_sp, v_ep)
        line.Layer = layer
        return line

    print("--- 1. Grids & Structures ---")
    draw_line([base_x, base_y - 1000, 0], [base_x, base_y + height + 2000, 0], "중심선")
    draw_line([base_x + span, base_y - 1000, 0], [base_x + span, base_y + height + 2000, 0], "중심선")
    draw_line([base_x - 2000, base_y, 0], [base_x + span + 2000, base_y, 0], "중심선")

    draw_line([base_x - 200, base_y, 0], [base_x - 200, base_y + height, 0], "COL")
    draw_line([base_x + 200, base_y, 0], [base_x + 200, base_y + height, 0], "COL")
    draw_line([base_x + span - 200, base_y, 0], [base_x + span - 200, base_y + height, 0], "COL")
    draw_line([base_x + span + 200, base_y, 0], [base_x + span + 200, base_y + height, 0], "COL")

    draw_line([base_x - 200, base_y + height, 0], [base_x + half_span, ridge_y, 0], "COL")
    draw_line([base_x + span + 200, base_y + height, 0], [base_x + half_span, ridge_y, 0], "COL")
    draw_line([base_x - 200, base_y + height - 400, 0], [base_x + half_span, ridge_y - 400, 0], "COL")
    draw_line([base_x + span + 200, base_y + height - 400, 0], [base_x + half_span, ridge_y - 400, 0], "COL")

    draw_line([base_x - 400, base_y + height + 100, 0], [base_x + half_span, ridge_y + 100, 0], "WALL1")
    draw_line([base_x + span + 400, base_y + height + 100, 0], [base_x + half_span, ridge_y + 100, 0], "WALL1")
    draw_line([base_x - 400, base_y + height + 280, 0], [base_x + half_span, ridge_y + 280, 0], "WALL1")
    draw_line([base_x + span + 400, base_y + height + 280, 0], [base_x + half_span, ridge_y + 280, 0], "WALL1")
    draw_line([base_x - 300, base_y, 0], [base_x - 300, base_y + height + 100, 0], "WALL1")
    draw_line([base_x - 400, base_y, 0], [base_x - 400, base_y + height + 100, 0], "WALL1")
    draw_line([base_x + span + 300, base_y, 0], [base_x + span + 300, base_y + height + 100, 0], "WALL1")
    draw_line([base_x + span + 400, base_y, 0], [base_x + span + 400, base_y + height + 100, 0], "WALL1")

    print("--- 2. Dimensions ---")
    def add_dim(pt1, pt2, loc_pt, angle):
        v_pt1 = win32com.client.VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_R8, pt1)
        v_pt2 = win32com.client.VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_R8, pt2)
        v_loc = win32com.client.VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_R8, loc_pt)
        dim = ms.AddDimRotated(v_pt1, v_pt2, v_loc, angle)
        dim.Layer = "치수"
        
    add_dim([base_x, base_y, 0], [base_x + span, base_y, 0], [base_x + half_span, base_y - 2000, 0], 0.0)
    add_dim([base_x, base_y, 0], [base_x, base_y + height, 0], [base_x - 2000, base_y + height/2, 0], math.pi/2)

    print("--- 3. Using Native QLEADER via AutoLISP ---")
    # QLEADER 리습 파일 생성
    lisp_path = os.path.abspath("temp_qleader.lsp").replace("\\", "/")
    leaders = [
        {"p1": [base_x + 3000, base_y + height + 400], "p2": [base_x + 4000, base_y + height + 1200], "p3": [base_x + 6000, base_y + height + 1200], "txt": "T180 그라스울 판넬(지붕)"},
        {"p1": [base_x - 350, base_y + 5000], "p2": [base_x - 1500, base_y + 5500], "p3": [base_x - 4000, base_y + 5500], "txt": "T100 그라스울 벽판넬"},
        {"p1": [base_x, base_y + 7000], "p2": [base_x + 1500, base_y + 7500], "p3": [base_x + 3500, base_y + 7500], "txt": "H-400x200x8x13"}
    ]
    
    lisp_code = "(defun c:DrawMyLeaders ( / oldlayer)\n"
    lisp_code += "  (setq oldlayer (getvar \"CLAYER\"))\n"
    lisp_code += "  (command \"-layer\" \"m\" \"치수\" \"\")\n"
    
    for ldr in leaders:
        # QLEADER 3-point format
        lisp_code += f'  (command "_.QLEADER" (list {ldr["p1"][0]} {ldr["p1"][1]}) (list {ldr["p2"][0]} {ldr["p2"][1]}) (list {ldr["p3"][0]} {ldr["p3"][1]}) "" "{ldr["txt"]}" "")\n'
        
    lisp_code += "  (setvar \"CLAYER\" oldlayer)\n"
    lisp_code += "  (princ)\n)\n"
    
    with open("temp_qleader.lsp", "w", encoding="euc-kr") as f:
        f.write(lisp_code)
        
    # 리습 로드 및 실행
    doc.SendCommand(f'(load "{lisp_path}")\n')
    doc.SendCommand("DrawMyLeaders\n")

    print("--- 4. Inserting ZIUM SHEET Block ---")
    try:
        # 스케일이 1000배 너무 컸으므로 ScaleFactor를 1.0으로 삽입 (단면도를 감싸게 위치 조정)
        v_ins = win32com.client.VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_R8, [base_x - 4000, base_y - 4000, 0.0])
        blk = ms.InsertBlock(v_ins, "ZIUM_sheet_architect", 1.0, 1.0, 1.0, 0.0)
        print("Successfully inserted ZIUM_sheet_architect with Scale 1.0!")
    except Exception as e:
        print(f"Block Insert failed: {e}")
        
    zoom_min = [base_x - 5000, base_y - 5000, 0]
    zoom_max = [base_x + span + 5000, base_y + height + 5000, 0]
    v_zmin = win32com.client.VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_R8, zoom_min)
    v_zmax = win32com.client.VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_R8, zoom_max)
    try:
        app.ZoomWindow(v_zmin, v_zmax)
    except:
        pass

    doc.Regen(1)
    print("Final QLEADER generation complete!")

if __name__ == "__main__":
    generate_perfect_qleader_section()
