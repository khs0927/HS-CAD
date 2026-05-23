# -*- coding: utf-8 -*-
import win32com.client
import pythoncom
import sys
import math

def generate_perfect_zium_section():
    print("Connecting to ZWCAD...")
    try:
        app = win32com.client.GetActiveObject("ZWCAD.Application")
        doc = app.ActiveDocument
        ms = doc.ModelSpace
    except Exception as e:
        sys.exit(1)
        
    print(f"Active Document: {doc.Name}")
    
    # 1. 단면도 작도 기준 위치 설정 (이전과 완전히 다른 깨끗한 새 공간)
    base_x = 450000.0
    base_y = 200000.0
    height = 10000.0
    span = 10000.0
    half_span = span / 2.0
    slope = 0.1
    ridge_y = base_y + height + (half_span * slope)
    
    # 2. 필수 레이어 세팅 (지움건축 문법 참조)
    layers = {
        "COL": 2,      # Yellow (기둥/보)
        "WALL1": 2,    # Yellow (벽체/단열선)
        "중심선": 1,    # Red (그리드)
        "치수": 7,     # White (치수 및 지시선)
        "글씨": 3      # Green (텍스트)
    }
    for l_name, color in layers.items():
        try:
            l_obj = doc.Layers.Add(l_name)
            l_obj.Color = color
        except:
            pass
            
    # 현재 활성 치수 스타일 설정
    try:
        if "300DIM" in [d.Name for d in doc.DimStyles]:
            doc.ActiveDimStyle = doc.DimStyles.Item("300DIM")
        elif "100DIM" in [d.Name for d in doc.DimStyles]:
            doc.ActiveDimStyle = doc.DimStyles.Item("100DIM")
    except:
        pass

    def draw_line(sp, ep, layer):
        v_sp = win32com.client.VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_R8, sp)
        v_ep = win32com.client.VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_R8, ep)
        line = ms.AddLine(v_sp, v_ep)
        line.Layer = layer
        return line

    print("--- 1. Drafting Grids & Main Structures ---")
    draw_line([base_x, base_y - 1000, 0], [base_x, base_y + height + 2000, 0], "중심선")
    draw_line([base_x + span, base_y - 1000, 0], [base_x + span, base_y + height + 2000, 0], "중심선")
    draw_line([base_x - 2000, base_y, 0], [base_x + span + 2000, base_y, 0], "중심선")

    # Columns
    draw_line([base_x - 200, base_y, 0], [base_x - 200, base_y + height, 0], "COL")
    draw_line([base_x + 200, base_y, 0], [base_x + 200, base_y + height, 0], "COL")
    draw_line([base_x + span - 200, base_y, 0], [base_x + span - 200, base_y + height, 0], "COL")
    draw_line([base_x + span + 200, base_y, 0], [base_x + span + 200, base_y + height, 0], "COL")

    # Rafters
    draw_line([base_x - 200, base_y + height, 0], [base_x + half_span, ridge_y, 0], "COL")
    draw_line([base_x + span + 200, base_y + height, 0], [base_x + half_span, ridge_y, 0], "COL")
    draw_line([base_x - 200, base_y + height - 400, 0], [base_x + half_span, ridge_y - 400, 0], "COL")
    draw_line([base_x + span + 200, base_y + height - 400, 0], [base_x + half_span, ridge_y - 400, 0], "COL")

    # Insulation (WALL1)
    draw_line([base_x - 400, base_y + height + 100, 0], [base_x + half_span, ridge_y + 100, 0], "WALL1")
    draw_line([base_x + span + 400, base_y + height + 100, 0], [base_x + half_span, ridge_y + 100, 0], "WALL1")
    draw_line([base_x - 400, base_y + height + 280, 0], [base_x + half_span, ridge_y + 280, 0], "WALL1")
    draw_line([base_x + span + 400, base_y + height + 280, 0], [base_x + half_span, ridge_y + 280, 0], "WALL1")
    draw_line([base_x - 300, base_y, 0], [base_x - 300, base_y + height + 100, 0], "WALL1")
    draw_line([base_x - 400, base_y, 0], [base_x - 400, base_y + height + 100, 0], "WALL1")
    draw_line([base_x + span + 300, base_y, 0], [base_x + span + 300, base_y + height + 100, 0], "WALL1")
    draw_line([base_x + span + 400, base_y, 0], [base_x + span + 400, base_y + height + 100, 0], "WALL1")

    print("--- 2. Drafting Dimensions (치수선) ---")
    def add_dim_rotated(pt1, pt2, loc_pt, angle, text_override=""):
        v_pt1 = win32com.client.VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_R8, pt1)
        v_pt2 = win32com.client.VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_R8, pt2)
        v_loc = win32com.client.VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_R8, loc_pt)
        dim = ms.AddDimRotated(v_pt1, v_pt2, v_loc, angle)
        dim.Layer = "치수"
        if text_override:
            dim.TextOverride = text_override
            
    # 폭 치수 (수평, angle=0)
    add_dim_rotated([base_x, base_y, 0], [base_x + span, base_y, 0], [base_x + half_span, base_y - 2000, 0], 0.0)
    
    # 높이 치수 (수직, angle=pi/2)
    add_dim_rotated([base_x, base_y, 0], [base_x, base_y + height, 0], [base_x - 2000, base_y + height/2, 0], math.pi/2)

    print("--- 3. Using AutoLISP QLEADER Method (지시선) ---")
    # LISP를 이용해 QLEADER를 그리는 스크립트 작성 및 주입
    # 이 방식은 사용자가 언급한 "XICAD 리습 또는 QLEADER" 방식을 완벽히 흉내냄
    lisp_code = """
(defun c:DrawMyQLeader (x1 y1 x2 y2 txt / oldlayer)
  (setq oldlayer (getvar "CLAYER"))
  (command "-layer" "m" "치수" "")
  (command "_.QLEADER" (list x1 y1) (list x2 y2) "" "" txt "")
  (setvar "CLAYER" oldlayer)
  (princ)
)
"""
    # LISP 로드 (가상 파일 없이 직접 실행하려면 조금 복잡하므로 SendCommand 활용)
    def send_qleader(x1, y1, x2, y2, text):
        # QLEADER 명령어 시퀀스를 SendCommand로 주입
        # 3점 클릭, 엔터, 텍스트입력, 엔터엔터
        cmd = f"_.QLEADER\n{x1},{y1}\n{x2},{y2}\n\n{text}\n\n"
        try:
            doc.SendCommand(cmd)
        except:
            pass

    # QLEADER 1: 지붕
    send_qleader(base_x + 3000, base_y + height + 400, base_x + 4000, base_y + height + 1500, "T180 그라스울 판넬(지붕)")
    # QLEADER 2: 벽체
    send_qleader(base_x - 350, base_y + 5000, base_x - 1500, base_y + 5500, "T100 그라스울 벽판넬")
    # QLEADER 3: 철골 
    send_qleader(base_x, base_y + 7000, base_x + 1500, base_y + 7500, "H-400x200x8x13")

    print("--- 4. Inserting ZIUM SHEET Block (도곽 삽입) ---")
    # 지음 도곽 블록 삽입 (ZIUM_sheet_architect)
    # 스케일 100.0 
    try:
        v_ins = win32com.client.VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_R8, [base_x - 2000, base_y - 4000, 0.0])
        blk = ms.InsertBlock(v_ins, "ZIUM_sheet_architect", 100.0, 100.0, 100.0, 0.0)
        blk.Layer = "0"
        print("Successfully inserted ZIUM_sheet_architect block!")
    except Exception as e:
        print(f"Failed to insert block: {e}")
        
    print("--- 5. Zoom Window ---")
    zoom_min = [base_x - 6000, base_y - 6000, 0]
    zoom_max = [base_x + span + 6000, base_y + height + 6000, 0]
    v_zmin = win32com.client.VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_R8, zoom_min)
    v_zmax = win32com.client.VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_R8, zoom_max)
    try:
        app.ZoomWindow(v_zmin, v_zmax)
    except:
        pass

    doc.Regen(1)
    print("Generation complete!")

if __name__ == "__main__":
    generate_perfect_zium_section()
