# -*- coding: utf-8 -*-
import win32com.client
import pythoncom
import sys
import math
import os

def draw_smart_section():
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
        
    # --- 1. 평면도 상태 파악 (좌표 및 위치 추론) ---
    print("--- 1. Inferring Floor Plan Coordinates ---")
    # 이전 스캔에서 파악된 평면도 메인 기둥 스팬: X=215977.2 ~ X=226117.7 (스팬 10,140.5)
    # 평면도 Y 좌표는 대략 300,000 부근으로 추정됨.
    # 따라서 단면도는 평면도 바로 아래로 수직 투영(Projection)하여 Y=250000 위치에 작도!
    col_x_left = 215977.2
    col_x_right = 226117.7
    span = col_x_right - col_x_left # 10140.5
    
    base_x = col_x_left
    base_y = 250000.0 # 평면도 바로 아래의 빈 공간
    height = 10000.0
    half_span = span / 2.0
    slope = 0.1
    ridge_y = base_y + height + (half_span * slope) # 지붕 용마루 높이
    
    print(f"Floor Plan inferred at X: {col_x_left}~{col_x_right}. Projecting Section to Y: {base_y}")

    # --- 2. 레이어 동기화 (평면도 레이어 상속) ---
    layers = {
        "COL": 2, "WALL1": 2, "중심선": 1, "치수": 7, "글씨": 3, "0": 7
    }
    for l_name, color in layers.items():
        try:
            doc.Layers.Add(l_name).Color = color
        except:
            pass

    def draw_line(sp, ep, layer):
        v_sp = win32com.client.VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_R8, sp)
        v_ep = win32com.client.VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_R8, ep)
        line = ms.AddLine(v_sp, v_ep)
        line.Layer = layer
        return line

    # --- 3. 디테일 단면도 작도 (H빔 단선 문제 및 단열재 뚫림 해결) ---
    print("--- 2. Drafting Highly Detailed Structures (Capped) ---")
    # 중심선
    draw_line([base_x, base_y - 1000, 0], [base_x, base_y + height + 2000, 0], "중심선")
    draw_line([col_x_right, base_y - 1000, 0], [col_x_right, base_y + height + 2000, 0], "중심선")
    draw_line([base_x - 2000, base_y, 0], [col_x_right + 2000, base_y, 0], "중심선")

    # H-Beam Columns (완벽한 사각 박스 마감 처리)
    col_width = 400.0
    cw2 = col_width / 2.0
    
    # Left Column
    draw_line([base_x - cw2, base_y, 0], [base_x - cw2, base_y + height, 0], "COL")
    draw_line([base_x + cw2, base_y, 0], [base_x + cw2, base_y + height, 0], "COL")
    draw_line([base_x - cw2, base_y, 0], [base_x + cw2, base_y, 0], "COL") # Bottom Cap
    draw_line([base_x - cw2, base_y + height, 0], [base_x + cw2, base_y + height, 0], "COL") # Top Cap
    
    # Right Column
    draw_line([col_x_right - cw2, base_y, 0], [col_x_right - cw2, base_y + height, 0], "COL")
    draw_line([col_x_right + cw2, base_y, 0], [col_x_right + cw2, base_y + height, 0], "COL")
    draw_line([col_x_right - cw2, base_y, 0], [col_x_right + cw2, base_y, 0], "COL") # Bottom Cap
    draw_line([col_x_right - cw2, base_y + height, 0], [col_x_right + cw2, base_y + height, 0], "COL") # Top Cap

    # Slope Rafters (완벽한 박스 마감 처리)
    # Left Rafter
    draw_line([base_x - cw2, base_y + height, 0], [base_x + half_span, ridge_y, 0], "COL")
    draw_line([base_x - cw2, base_y + height - col_width, 0], [base_x + half_span, ridge_y - col_width, 0], "COL")
    draw_line([base_x - cw2, base_y + height, 0], [base_x - cw2, base_y + height - col_width, 0], "COL") # Left Cap
    draw_line([base_x + half_span, ridge_y, 0], [base_x + half_span, ridge_y - col_width, 0], "COL") # Right Cap (Ridge)
    
    # Right Rafter
    draw_line([col_x_right + cw2, base_y + height, 0], [base_x + half_span, ridge_y, 0], "COL")
    draw_line([col_x_right + cw2, base_y + height - col_width, 0], [base_x + half_span, ridge_y - col_width, 0], "COL")
    draw_line([col_x_right + cw2, base_y + height, 0], [col_x_right + cw2, base_y + height - col_width, 0], "COL") # Right Cap

    # Roof Insulation (마감 처리된 완벽한 구역)
    draw_line([base_x - 400, base_y + height + 100, 0], [base_x + half_span, ridge_y + 100, 0], "WALL1")
    draw_line([col_x_right + 400, base_y + height + 100, 0], [base_x + half_span, ridge_y + 100, 0], "WALL1")
    draw_line([base_x - 400, base_y + height + 280, 0], [base_x + half_span, ridge_y + 280, 0], "WALL1")
    draw_line([col_x_right + 400, base_y + height + 280, 0], [base_x + half_span, ridge_y + 280, 0], "WALL1")
    # Caps
    draw_line([base_x - 400, base_y + height + 100, 0], [base_x - 400, base_y + height + 280, 0], "WALL1")
    draw_line([col_x_right + 400, base_y + height + 100, 0], [col_x_right + 400, base_y + height + 280, 0], "WALL1")
    draw_line([base_x + half_span, ridge_y + 100, 0], [base_x + half_span, ridge_y + 280, 0], "WALL1")

    # Wall Insulation (마감 처리된 완벽한 구역)
    draw_line([base_x - 300, base_y, 0], [base_x - 300, base_y + height + 100, 0], "WALL1")
    draw_line([base_x - 400, base_y, 0], [base_x - 400, base_y + height + 100, 0], "WALL1")
    draw_line([base_x - 300, base_y, 0], [base_x - 400, base_y, 0], "WALL1")
    draw_line([base_x - 300, base_y + height + 100, 0], [base_x - 400, base_y + height + 100, 0], "WALL1")
    
    draw_line([col_x_right + 300, base_y, 0], [col_x_right + 300, base_y + height + 100, 0], "WALL1")
    draw_line([col_x_right + 400, base_y, 0], [col_x_right + 400, base_y + height + 100, 0], "WALL1")
    draw_line([col_x_right + 300, base_y, 0], [col_x_right + 400, base_y, 0], "WALL1")
    draw_line([col_x_right + 300, base_y + height + 100, 0], [col_x_right + 400, base_y + height + 100, 0], "WALL1")

    # --- 4. 정규 치수선 배치 ---
    print("--- 3. Drafting Dimensions ---")
    def add_dim(pt1, pt2, loc_pt, angle):
        v_pt1 = win32com.client.VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_R8, pt1)
        v_pt2 = win32com.client.VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_R8, pt2)
        v_loc = win32com.client.VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_R8, loc_pt)
        dim = ms.AddDimRotated(v_pt1, v_pt2, v_loc, angle)
        dim.Layer = "치수"
        
    add_dim([base_x, base_y, 0], [col_x_right, base_y, 0], [base_x + half_span, base_y - 2000, 0], 0.0)
    add_dim([base_x, base_y, 0], [base_x, base_y + height, 0], [base_x - 2000, base_y + height/2, 0], math.pi/2)

    # --- 5. 완벽한 도곽 정중앙 배치 (위치 오류 수정) ---
    print("--- 4. Centering Title Block (ZIUM_sheet_architect) ---")
    # 단면도의 정중앙 좌표 계산
    center_x = base_x + half_span
    center_y = base_y + (height / 2.0)
    # Scale 0.5로 설정 시 도곽의 실제 크기가 대략 21,000 x 14,850이 되므로 이를 단면도를 감싸도록 배치
    insert_x = center_x - 11000.0
    insert_y = center_y - 8000.0
    
    try:
        v_ins = win32com.client.VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_R8, [insert_x, insert_y, 0.0])
        blk = ms.InsertBlock(v_ins, "ZIUM_sheet_architect", 0.5, 0.5, 0.5, 0.0)
        blk.Layer = "0"
        print("Successfully centered ZIUM_sheet_architect with Scale 0.5!")
    except Exception as e:
        print(f"Block Insert failed: {e}")

    # --- 6. 완벽한 지시선 처리 (클래식 LEADER 명령 주입) ---
    # QLEADER 설정 무시, 확실한 3-point LEADER 명령을 사용하여 꺾임선(Dogleg) 보장!
    print("--- 5. Generating Perfect Classic Leaders ---")
    lisp_path = os.path.abspath("temp_smart_leader.lsp").replace("\\", "/")
    leaders = [
        {"p1": [base_x + 3000, base_y + height + 400], "p2": [base_x + 4000, base_y + height + 1500], "p3": [base_x + 7000, base_y + height + 1500], "txt": "T180 그라스울 판넬(지붕)"},
        {"p1": [base_x - 350, base_y + 5000], "p2": [base_x - 1500, base_y + 6000], "p3": [base_x - 4500, base_y + 6000], "txt": "T100 그라스울 벽판넬"},
        {"p1": [base_x, base_y + 7000], "p2": [base_x + 1500, base_y + 8000], "p3": [base_x + 4500, base_y + 8000], "txt": "H-400x200x8x13"}
    ]
    
    lisp_code = "(defun c:DrawSmartLeaders ( / oldlayer)\n"
    lisp_code += "  (setq oldlayer (getvar \"CLAYER\"))\n"
    lisp_code += "  (command \"-layer\" \"m\" \"치수\" \"\")\n"
    lisp_code += "  (setvar \"DIMTAD\" 1)\n" # 텍스트를 지시선 위에 배치
    
    for ldr in leaders:
        # _.LEADER command strictly forces points
        lisp_code += f'  (command "_.LEADER" (list {ldr["p1"][0]} {ldr["p1"][1]}) (list {ldr["p2"][0]} {ldr["p2"][1]}) (list {ldr["p3"][0]} {ldr["p3"][1]}) "" "{ldr["txt"]}" "")\n'
        
    lisp_code += "  (setvar \"CLAYER\" oldlayer)\n"
    lisp_code += "  (princ)\n)\n"
    
    with open("temp_smart_leader.lsp", "w", encoding="euc-kr") as f:
        f.write(lisp_code)
        
    doc.SendCommand(f'(load "{lisp_path}")\n')
    doc.SendCommand("DrawSmartLeaders\n")

    # --- 7. 화면 이동 (Zoom Focus) ---
    print("--- 6. Focusing Screen ---")
    zoom_min = [insert_x - 2000, insert_y - 2000, 0]
    zoom_max = [insert_x + 25000, insert_y + 20000, 0]
    v_zmin = win32com.client.VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_R8, zoom_min)
    v_zmax = win32com.client.VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_R8, zoom_max)
    try:
        app.ZoomWindow(v_zmin, v_zmax)
    except:
        pass

    doc.Regen(1)
    print("Smart Section Generation completely successful!")

if __name__ == "__main__":
    draw_smart_section()
