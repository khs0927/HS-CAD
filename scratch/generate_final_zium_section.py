# -*- coding: utf-8 -*-
import win32com.client
import pythoncom
import sys
import math

def generate_final_zium_section():
    try:
        app = win32com.client.GetActiveObject("ZWCAD.Application")
        doc = app.ActiveDocument
        ms = doc.ModelSpace
    except Exception as e:
        sys.exit(1)
        
    # 취소 키 전송 (명령어 대기 상태 해제)
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

    # 1. Grids & Structures
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

    # 2. Dimensions
    def add_dim(pt1, pt2, loc_pt, angle):
        v_pt1 = win32com.client.VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_R8, pt1)
        v_pt2 = win32com.client.VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_R8, pt2)
        v_loc = win32com.client.VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_R8, loc_pt)
        dim = ms.AddDimRotated(v_pt1, v_pt2, v_loc, angle)
        dim.Layer = "치수"
        
    add_dim([base_x, base_y, 0], [base_x + span, base_y, 0], [base_x + half_span, base_y - 2000, 0], 0.0)
    add_dim([base_x, base_y, 0], [base_x, base_y + height, 0], [base_x - 2000, base_y + height/2, 0], math.pi/2)

    # 3. Leaders
    def add_leader(start, land, end, text):
        v_end = win32com.client.VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_R8, end)
        mtext = ms.AddMText(v_end, 0.0, text)
        mtext.Height = 250.0
        mtext.Layer = "치수"
        
        pts = list(start) + list(land) + list(end)
        v_pts = win32com.client.VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_R8, pts)
        
        leader = ms.AddLeader(v_pts, mtext, 1)
        leader.Layer = "치수"

    add_leader([base_x + 3000, base_y + height + 400, 0], [base_x + 4000, base_y + height + 1200, 0], [base_x + 7000, base_y + height + 1200, 0], "T180 그라스울 판넬(지붕)")
    add_leader([base_x - 350, base_y + 5000, 0], [base_x - 1500, base_y + 5500, 0], [base_x - 4500, base_y + 5500, 0], "T100 그라스울 벽판넬")
    add_leader([base_x, base_y + 7000, 0], [base_x + 1500, base_y + 7500, 0], [base_x + 4500, base_y + 7500, 0], "H-400x200x8x13")

    # 4. Insert Block
    try:
        # 단면도와 겹치지 않게 좌하단에 배치, 스케일 100
        v_ins = win32com.client.VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_R8, [base_x - 10000, base_y - 10000, 0.0])
        blk = ms.InsertBlock(v_ins, "ZIUM_sheet_architect", 100.0, 100.0, 100.0, 0.0)
    except Exception as e:
        print(f"Block Insert failed: {e}")
        
    zoom_min = [base_x - 12000, base_y - 12000, 0]
    zoom_max = [base_x + span + 12000, base_y + height + 12000, 0]
    v_zmin = win32com.client.VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_R8, zoom_min)
    v_zmax = win32com.client.VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_R8, zoom_max)
    try:
        app.ZoomWindow(v_zmin, v_zmax)
    except:
        pass

    doc.Regen(1)
    print("Final generation complete!")

if __name__ == "__main__":
    generate_final_zium_section()
