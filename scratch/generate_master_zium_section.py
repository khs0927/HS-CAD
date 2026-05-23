# -*- coding: utf-8 -*-
import win32com.client
import pythoncom
import sys
import math
import os

def generate_master_zium_section():
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
        "COL": 2, "WALL1": 2, "중심선": 1, "치수": 7, "글씨": 3, "0": 7
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

    print("--- 1. Cleaning up previous generation ---")
    # 400000~500000 영역 삭제
    for i in range(ms.Count - 1, -1, -1):
        try:
            ent = ms.Item(i)
            x = None
            if hasattr(ent, 'InsertionPoint'): x = ent.InsertionPoint[0]
            elif hasattr(ent, 'StartPoint'): x = ent.StartPoint[0]
            elif hasattr(ent, 'Coordinates'): x = ent.Coordinates[0]
            if x is not None and 400000.0 < x < 500000.0:
                ent.Delete()
        except:
            pass

    print("--- 2. Drafting Grids & Detailed Structures ---")
    # 중심선
    draw_line([base_x, base_y - 1000, 0], [base_x, base_y + height + 2000, 0], "중심선")
    draw_line([base_x + span, base_y - 1000, 0], [base_x + span, base_y + height + 2000, 0], "중심선")
    draw_line([base_x - 2000, base_y, 0], [base_x + span + 2000, base_y, 0], "중심선")

    # H-Beam Columns (Capped ends)
    # Left Column
    draw_line([base_x - 200, base_y, 0], [base_x - 200, base_y + height, 0], "COL")
    draw_line([base_x + 200, base_y, 0], [base_x + 200, base_y + height, 0], "COL")
    draw_line([base_x - 200, base_y, 0], [base_x + 200, base_y, 0], "COL") # Bottom cap
    draw_line([base_x - 200, base_y + height, 0], [base_x + 200, base_y + height, 0], "COL") # Top cap
    
    # Right Column
    draw_line([base_x + span - 200, base_y, 0], [base_x + span - 200, base_y + height, 0], "COL")
    draw_line([base_x + span + 200, base_y, 0], [base_x + span + 200, base_y + height, 0], "COL")
    draw_line([base_x + span - 200, base_y, 0], [base_x + span + 200, base_y, 0], "COL") # Bottom cap
    draw_line([base_x + span - 200, base_y + height, 0], [base_x + span + 200, base_y + height, 0], "COL") # Top cap

    # Rafter Beams (Capped ends)
    # Left Rafter
    draw_line([base_x - 200, base_y + height, 0], [base_x + half_span, ridge_y, 0], "COL")
    draw_line([base_x - 200, base_y + height - 400, 0], [base_x + half_span, ridge_y - 400, 0], "COL")
    draw_line([base_x - 200, base_y + height, 0], [base_x - 200, base_y + height - 400, 0], "COL") # Left cap
    draw_line([base_x + half_span, ridge_y, 0], [base_x + half_span, ridge_y - 400, 0], "COL") # Right cap (Ridge center)
    
    # Right Rafter
    draw_line([base_x + span + 200, base_y + height, 0], [base_x + half_span, ridge_y, 0], "COL")
    draw_line([base_x + span + 200, base_y + height - 400, 0], [base_x + half_span, ridge_y - 400, 0], "COL")
    draw_line([base_x + span + 200, base_y + height, 0], [base_x + span + 200, base_y + height - 400, 0], "COL") # Right cap
    # (Left cap at ridge already drawn)

    # Roof Insulation (WALL1 - Capped)
    draw_line([base_x - 400, base_y + height + 100, 0], [base_x + half_span, ridge_y + 100, 0], "WALL1")
    draw_line([base_x + span + 400, base_y + height + 100, 0], [base_x + half_span, ridge_y + 100, 0], "WALL1")
    draw_line([base_x - 400, base_y + height + 280, 0], [base_x + half_span, ridge_y + 280, 0], "WALL1")
    draw_line([base_x + span + 400, base_y + height + 280, 0], [base_x + half_span, ridge_y + 280, 0], "WALL1")
    
    # Roof insulation caps
    draw_line([base_x - 400, base_y + height + 100, 0], [base_x - 400, base_y + height + 280, 0], "WALL1") # Left outer cap
    draw_line([base_x + span + 400, base_y + height + 100, 0], [base_x + span + 400, base_y + height + 280, 0], "WALL1") # Right outer cap
    draw_line([base_x + half_span, ridge_y + 100, 0], [base_x + half_span, ridge_y + 280, 0], "WALL1") # Ridge cap

    # Wall Insulation (WALL1 - Capped)
    # Left Wall
    draw_line([base_x - 300, base_y, 0], [base_x - 300, base_y + height + 100, 0], "WALL1")
    draw_line([base_x - 400, base_y, 0], [base_x - 400, base_y + height + 100, 0], "WALL1")
    draw_line([base_x - 300, base_y, 0], [base_x - 400, base_y, 0], "WALL1") # Bottom cap
    draw_line([base_x - 300, base_y + height + 100, 0], [base_x - 400, base_y + height + 100, 0], "WALL1") # Top cap
    
    # Right Wall
    draw_line([base_x + span + 300, base_y, 0], [base_x + span + 300, base_y + height + 100, 0], "WALL1")
    draw_line([base_x + span + 400, base_y, 0], [base_x + span + 400, base_y + height + 100, 0], "WALL1")
    draw_line([base_x + span + 300, base_y, 0], [base_x + span + 400, base_y, 0], "WALL1") # Bottom cap
    draw_line([base_x + span + 300, base_y + height + 100, 0], [base_x + span + 400, base_y + height + 100, 0], "WALL1") # Top cap

    print("--- 3. Dimensions ---")
    def add_dim(pt1, pt2, loc_pt, angle):
        v_pt1 = win32com.client.VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_R8, pt1)
        v_pt2 = win32com.client.VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_R8, pt2)
        v_loc = win32com.client.VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_R8, loc_pt)
        dim = ms.AddDimRotated(v_pt1, v_pt2, v_loc, angle)
        dim.Layer = "치수"
        
    add_dim([base_x, base_y, 0], [base_x + span, base_y, 0], [base_x + half_span, base_y - 2000, 0], 0.0)
    add_dim([base_x, base_y, 0], [base_x, base_y + height, 0], [base_x - 2000, base_y + height/2, 0], math.pi/2)

    print("--- 4. Using Classic LEADER Command via LISP ---")
    # LEADER 명령어를 사용하면 무조건 꺾임선(Dogleg)과 문자가 제대로 결합됩니다.
    lisp_path = os.path.abspath("temp_leader.lsp").replace("\\", "/")
    leaders = [
        {"p1": [base_x + 3000, base_y + height + 400], "p2": [base_x + 4000, base_y + height + 1200], "p3": [base_x + 6000, base_y + height + 1200], "txt": "T180 그라스울 판넬(지붕)"},
        {"p1": [base_x - 350, base_y + 5000], "p2": [base_x - 1500, base_y + 5500], "p3": [base_x - 3500, base_y + 5500], "txt": "T100 그라스울 벽판넬"},
        {"p1": [base_x, base_y + 7000], "p2": [base_x + 1500, base_y + 7500], "p3": [base_x + 3500, base_y + 7500], "txt": "H-400x200x8x13"}
    ]
    
    lisp_code = "(defun c:DrawMyClassicLeaders ( / oldlayer)\n"
    lisp_code += "  (setq oldlayer (getvar \"CLAYER\"))\n"
    lisp_code += "  (command \"-layer\" \"m\" \"치수\" \"\")\n"
    
    for ldr in leaders:
        # Classic LEADER: pt1 pt2 pt3 Enter txt Enter
        lisp_code += f'  (command "_.LEADER" (list {ldr["p1"][0]} {ldr["p1"][1]}) (list {ldr["p2"][0]} {ldr["p2"][1]}) (list {ldr["p3"][0]} {ldr["p3"][1]}) "" "{ldr["txt"]}" "")\n'
        
    lisp_code += "  (setvar \"CLAYER\" oldlayer)\n"
    lisp_code += "  (princ)\n)\n"
    
    with open("temp_leader.lsp", "w", encoding="euc-kr") as f:
        f.write(lisp_code)
        
    # 리습 로드 및 실행
    doc.SendCommand(f'(load "{lisp_path}")\n')
    doc.SendCommand("DrawMyClassicLeaders\n")

    print("--- 5. Inserting ZIUM SHEET Block (Proper Scale 0.6) ---")
    try:
        # ZIUM_sheet_architect 블록을 Scale 0.6 으로 삽입하여 도곽 크기를 정확히 맞춤
        v_ins = win32com.client.VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_R8, [base_x - 10000, base_y - 8000, 0.0])
        blk = ms.InsertBlock(v_ins, "ZIUM_sheet_architect", 0.6, 0.6, 0.6, 0.0)
        blk.Layer = "0"
        print("Successfully inserted ZIUM_sheet_architect with Scale 0.6!")
    except Exception as e:
        print(f"Block Insert failed: {e}")
        
    print("--- 6. Zoom Window ---")
    zoom_min = [base_x - 12000, base_y - 12000, 0]
    zoom_max = [base_x + span + 12000, base_y + height + 12000, 0]
    v_zmin = win32com.client.VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_R8, zoom_min)
    v_zmax = win32com.client.VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_R8, zoom_max)
    try:
        app.ZoomWindow(v_zmin, v_zmax)
    except:
        pass

    doc.Regen(1)
    print("Master generation complete!")

if __name__ == "__main__":
    generate_master_zium_section()
