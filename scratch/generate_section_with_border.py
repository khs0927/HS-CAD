# -*- coding: utf-8 -*-
import win32com.client
import pythoncom
import sys

def generate_section_with_border():
    print("Connecting to ZWCAD for Sheet Border & Zoom...")
    try:
        app = win32com.client.GetActiveObject("ZWCAD.Application")
        doc = app.ActiveDocument
        ms = doc.ModelSpace
    except Exception as e:
        print(f"Connection Error: {e}")
        sys.exit(1)
        
    print(f"Active Document: {doc.Name}")
    
    # 1. 단면도 및 도곽 배치 기준 좌표
    base_x = 350000.0
    base_y = 200000.0
    span = 10000.0
    height = 10000.0
    
    # 2. BORDER 레이어 생성 (색상: 5 / Blue, 도곽 표준색상)
    border_layer = "BORDER"
    try:
        l_obj = doc.Layers.Add(border_layer)
        l_obj.Color = 5 # Blue
    except:
        pass
        
    try:
        doc.Layers.Add("TXT").Color = 4 # Cyan
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

    print("\n--- 1. Drafting Sheet Border (A3 Size Scaled 1:100) ---")
    # A3 규격 (420 x 297) -> 1:100 축척 환산 시 (42,000 x 29,700)
    # 단면도를 중심으로 잡기 위한 도곽 좌측 하단 시작점 계산
    border_w = 42000.0
    border_h = 29700.0
    
    bx = base_x - 12000.0
    by = base_y - 8000.0
    
    # 외곽 테두리선
    draw_line([bx, by, 0], [bx + border_w, by, 0], border_layer)
    draw_line([bx + border_w, by, 0], [bx + border_w, by + border_h, 0], border_layer)
    draw_line([bx + border_w, by + border_h, 0], [bx, by + border_h, 0], border_layer)
    draw_line([bx, by + border_h, 0], [bx, by, 0], border_layer)
    
    # 내측 여백선 (Offset 10mm -> 1000mm)
    ix, iy = bx + 1000.0, by + 1000.0
    iw, ih = border_w - 2000.0, border_h - 2000.0
    
    draw_line([ix, iy, 0], [ix + iw, iy, 0], border_layer)
    draw_line([ix + iw, iy, 0], [ix + iw, iy + ih, 0], border_layer)
    draw_line([ix + iw, iy + ih, 0], [ix, iy + ih, 0], border_layer)
    draw_line([ix, iy + ih, 0], [ix, iy, 0], border_layer)

    print("--- 2. Drafting Professional Title Block (표제란) ---")
    # 우측 하단 구석에 표제란 작성 (가로 8000mm, 세로 3000mm)
    tx_start = ix + iw - 8000.0
    ty_start = iy
    
    # 표제란 외곽선
    draw_line([tx_start, ty_start + 3000, 0], [ix + iw, ty_start + 3000, 0], border_layer)
    draw_line([tx_start, ty_start, 0], [tx_start, ty_start + 3000, 0], border_layer)
    
    # 표제란 격자 칸막이선
    draw_line([tx_start + 2000, ty_start, 0], [tx_start + 2000, ty_start + 3000, 0], border_layer)
    draw_line([tx_start, ty_start + 1500, 0], [ix + iw, ty_start + 1500, 0], border_layer)
    
    # 표제란 텍스트 기입 (TXT 레이어)
    def add_title_text(text, pt, height=250.0):
        v_pt = win32com.client.VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_R8, pt)
        t_obj = ms.AddMText(v_pt, 0.0, text)
        t_obj.Height = height
        t_obj.Layer = "TXT"
        # 중간 중심 정렬
        t_obj.AttachmentPoint = 5 # acAttachmentPointMiddleCenter
        
    add_title_text("도 면 명", [tx_start + 1000, ty_start + 2250, 0], 200.0)
    add_title_text("종단면 상세도 (S=1:100)", [tx_start + 5000, ty_start + 2250, 0], 250.0)
    
    add_title_text("설 계 자", [tx_start + 1000, ty_start + 750, 0], 200.0)
    add_title_text("지음건축사사무소 (Jieum)", [tx_start + 5000, ty_start + 750, 0], 250.0)

    print("--- 3. Focusing Screen to Created Section Sheet (Zoom Window) ---")
    # 도곽 영역에 맞추어 화면을 정교하게 줌인(Focusing)
    # 여백을 약간 주어 줌처리
    zoom_min = [bx - 2000.0, by - 2000.0, 0.0]
    zoom_max = [bx + border_w + 2000.0, by + border_h + 2000.0, 0.0]
    
    v_zmin = win32com.client.VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_R8, zoom_min)
    v_zmax = win32com.client.VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_R8, zoom_max)
    
    try:
        app.ZoomWindow(v_zmin, v_zmax)
        print("ZWCAD viewport successfully updated and focused on the section drawing!")
    except Exception as ze:
        print(f"Zoom Window failed: {ze}")
        
    doc.Regen(1)
    print("\n--- All Layout & Zoom Operations Completed! ---")

if __name__ == "__main__":
    generate_section_with_border()
