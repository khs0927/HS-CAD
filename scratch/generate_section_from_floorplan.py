# -*- coding: utf-8 -*-
import win32com.client
import pythoncom
import sys
import math

def generate_section_from_floorplan():
    print("Connecting to ZWCAD for Section Generation...")
    try:
        app = win32com.client.GetActiveObject("ZWCAD.Application")
        doc = app.ActiveDocument
        ms = doc.ModelSpace
    except Exception as e:
        print(f"Connection Error: {e}")
        sys.exit(1)
        
    print(f"Active Document: {doc.Name}")
    
    # 1. 단면도 작도 기준 위치 설정 (평면도 우측 빈 공간)
    # 평면도 좌표계 X: 170000~270000 영역을 피해 X: 350000, Y: 200000 지점에 배치
    base_x = 350000.0
    base_y = 200000.0
    
    # 설계 스펙 정의 (높이 10M, 스팬 10M)
    height = 10000.0
    span = 10000.0
    half_span = span / 2.0
    slope = 0.1 # 1:10 (10%) 물매
    
    # 2. 레이어 정의 및 생성
    layers = {
        "COL": 2,      # Yellow (형강 구조체)
        "TXT": 4,      # Cyan (텍스트 및 지시선)
        "WALL": 5,     # Magenta (단열재 외곽선)
        "HATCH": 8,    # Gray (단열 스티플 및 기초 해치)
        "CEN": 1       # Red (중심선)
    }
    
    for l_name, color in layers.items():
        try:
            l_obj = doc.Layers.Add(l_name)
            l_obj.Color = color
        except:
            pass

    def draw_line(sp, ep, layer, color=None):
        v_sp = win32com.client.VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_R8, sp)
        v_ep = win32com.client.VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_R8, ep)
        line = ms.AddLine(v_sp, v_ep)
        line.Layer = layer
        if color is not None:
            line.Color = color
        return line

    print("\n--- 1. Drafting Grid Center Lines (CEN) ---")
    # 기둥 중심선 작성
    draw_line([base_x, base_y - 1000, 0], [base_x, base_y + height + 2000, 0], "CEN")
    draw_line([base_x + span, base_y - 1000, 0], [base_x + span, base_y + height + 2000, 0], "CEN")
    # 바닥 레벨선 (G.L / F.L)
    draw_line([base_x - 2000, base_y, 0], [base_x + span + 2000, base_y, 0], "CEN")

    print("--- 2. Drafting H-400x200 Columns (COL) ---")
    # 주 기둥: H-400x200x8x13 (단면상 폭 400 표현)
    col_width = 400.0
    # 좌측 기둥 (X: base_x - 200 ~ base_x + 200)
    draw_line([base_x - 200, base_y, 0], [base_x - 200, base_y + height, 0], "COL")
    draw_line([base_x + 200, base_y, 0], [base_x + 200, base_y + height, 0], "COL")
    # 우측 기둥 (X: base_x + span - 200 ~ base_x + span + 200)
    draw_line([base_x + span - 200, base_y, 0], [base_x + span - 200, base_y + height, 0], "COL")
    draw_line([base_x + span + 200, base_y, 0], [base_x + span + 200, base_y + height, 0], "COL")

    print("--- 3. Drafting Slope Rafter Beams (COL) ---")
    # 지붕 Rafter H-400x200 (물매 1:10 적용)
    # 기둥 상부 Y: base_y + height. 중앙 X: base_x + half_span
    ridge_y = base_y + height + (half_span * slope) # Y: 210000 + 500 = 210500
    
    # 보 상단 플랜지 라인
    draw_line([base_x - 200, base_y + height, 0], [base_x + half_span, ridge_y, 0], "COL")
    draw_line([base_x + span + 200, base_y + height, 0], [base_x + half_span, ridge_y, 0], "COL")
    
    # 보 하단 플랜지 라인 (부재 높이 400 고려하여 수직 오프셋 400)
    draw_line([base_x - 200, base_y + height - 400, 0], [base_x + half_span, ridge_y - 400, 0], "COL")
    draw_line([base_x + span + 200, base_y + height - 400, 0], [base_x + half_span, ridge_y - 400, 0], "COL")

    print("--- 4. Drafting T180 Roof Panels (WALL) ---")
    # 보 상단 위에 T180 그라스울 판넬 라인 드로잉
    draw_line([base_x - 400, base_y + height + 100, 0], [base_x + half_span, ridge_y + 100, 0], "WALL")
    draw_line([base_x + span + 400, base_y + height + 100, 0], [base_x + half_span, ridge_y + 100, 0], "WALL")
    
    draw_line([base_x - 400, base_y + height + 280, 0], [base_x + half_span, ridge_y + 280, 0], "WALL")
    draw_line([base_x + span + 400, base_y + height + 280, 0], [base_x + half_span, ridge_y + 280, 0], "WALL")

    print("--- 5. Drafting T100 Wall Panels (WALL) ---")
    # 기둥 외측에 T100 벽판넬 라인 드로잉 (두께 100)
    # 좌측 벽체
    draw_line([base_x - 300, base_y, 0], [base_x - 300, base_y + height + 100, 0], "WALL")
    draw_line([base_x - 400, base_y, 0], [base_x - 400, base_y + height + 100, 0], "WALL")
    # 우측 벽체
    draw_line([base_x + span + 300, base_y, 0], [base_x + span + 300, base_y + height + 100, 0], "WALL")
    draw_line([base_x + span + 400, base_y, 0], [base_x + span + 400, base_y + height + 100, 0], "WALL")

    print("--- 6. Drafting Foundations (WALL) ---")
    # 기초 콘크리트 패드 (두께 600, 폭 1200)
    # 좌측 기초
    draw_line([base_x - 600, base_y, 0], [base_x + 600, base_y, 0], "WALL")
    draw_line([base_x - 600, base_y - 600, 0], [base_x - 600, base_y, 0], "WALL")
    draw_line([base_x + 600, base_y - 600, 0], [base_x + 600, base_y, 0], "WALL")
    draw_line([base_x - 600, base_y - 600, 0], [base_x + 600, base_y - 600, 0], "WALL")
    # 우측 기초
    draw_line([base_x + span - 600, base_y, 0], [base_x + span + 600, base_y, 0], "WALL")
    draw_line([base_x + span - 600, base_y - 600, 0], [base_x + span - 600, base_y, 0], "WALL")
    draw_line([base_x + span + 600, base_y - 600, 0], [base_x + span + 600, base_y, 0], "WALL")
    draw_line([base_x + span - 600, base_y - 600, 0], [base_x + span + 600, base_y - 600, 0], "WALL")

    print("--- 7. Adding Professional AddLeader Annotations (TXT) ---")
    # 정규 지시선 작도 헬퍼 함수
    def add_leader(start, land, end, text):
        try:
            v_end = win32com.client.VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_R8, end)
            mtext = ms.AddMText(v_end, 0.0, text)
            mtext.Height = 250.0 # 스케일 맞춤
            mtext.Layer = "TXT"
            
            pts = list(start) + list(land) + list(end)
            v_pts = win32com.client.VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_R8, pts)
            
            leader = ms.AddLeader(v_pts, mtext, 1)
            leader.Layer = "TXT"
            print(f"Leader Created: {text}")
        except Exception as e:
            print(f"Leader Fail for '{text}': {e}")
            # Fallback
            draw_line(start, land, "TXT")
            draw_line(land, end, "TXT")
            v_pt = win32com.client.VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_R8, [end[0]+50, end[1]+50, end[2]])
            t_obj = ms.AddText(text, v_pt, 250.0)
            t_obj.Layer = "TXT"

    # 7.1 지붕 단열재 지시선 (T180 그라스울 판넬(지붕))
    add_leader(
        [base_x + 3000, base_y + height + 400, 0],
        [base_x + 4000, base_y + height + 1200, 0],
        [base_x + 7000, base_y + height + 1200, 0],
        "T180 그라스울 판넬(지붕) - 지음건축 S조 표준"
    )
    
    # 7.2 벽체 단열재 지시선 (T100 그라스울 벽판넬)
    add_leader(
        [base_x - 350, base_y + 5000, 0],
        [base_x - 1500, base_y + 5500, 0],
        [base_x - 4500, base_y + 5500, 0],
        "T100 그라스울 벽판넬 - 지음건축 S조 표준"
    )
    
    # 7.3 기둥 구조재 규격 지시선 (H-400x200x8x13)
    add_leader(
        [base_x, base_y + 7000, 0],
        [base_x + 1500, base_y + 7500, 0],
        [base_x + 4500, base_y + 7500, 0],
        "COL: H-400x200x8x13 (지음 표준 기둥)"
    )
    
    # 7.4 보/서까래 구조재 규격 지시선 (H-400x200x8x13)
    add_leader(
        [base_x + half_span, ridge_y - 200, 0],
        [base_x + half_span + 1500, ridge_y + 500, 0],
        [base_x + half_span + 4500, ridge_y + 500, 0],
        "RAFTER: H-400x200x8x13 (물매 1:10)"
    )

    # 7.5 실내재료마감 지시선
    add_leader(
        [base_x + 3000, base_y + 1500, 0],
        [base_x + 4500, base_y + 800, 0],
        [base_x + 7500, base_y + 800, 0],
        "실내재료마감 - ArchiOffice 표준"
    )

    # 8. 단면도 타이틀 텍스트 기입
    v_title_pt = win32com.client.VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_R8, [base_x + half_span - 1500, base_y - 1500, 0])
    title = ms.AddMText(v_title_pt, 0.0, "종단면도 상세 (S=1:100)")
    title.Height = 500.0
    title.Layer = "TXT"
    
    print("\n--- ZWCAD Section Generation Completed Successfully! ---")
    doc.Regen(1)

if __name__ == "__main__":
    generate_section_from_floorplan()
