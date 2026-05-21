# -*- coding: utf-8 -*-
import win32com.client
import pythoncom
import sys

def draw_jieum_section_leaders():
    print("Connecting to ZWCAD...")
    try:
        app = win32com.client.GetActiveObject("ZWCAD.Application")
        doc = app.ActiveDocument
        ms = doc.ModelSpace
    except Exception as e:
        print(f"Error connecting to ZWCAD: {e}")
        sys.exit(1)
        
    print(f"Connected to Active Document: {doc.Name}")

    # 1. 종단면도 자동 좌표 스캔 (Selection Set 활용)
    ss_name = "JieumScanSS"
    try:
        ss = doc.SelectionSets.Add(ss_name)
    except:
        ss = doc.SelectionSets.Item(ss_name)
        ss.Clear()
        
    f_type = win32com.client.VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_I2, [0])
    f_data = win32com.client.VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_VARIANT, ["TEXT,MTEXT"])
    ss.Select(5, None, None, f_type, f_data)
    
    base_x, base_y = None, None
    for i in range(ss.Count):
        try:
            ent = ss.Item(i)
            txt = ent.TextString
            # 깨진 한글이거나 인코딩 고려하여 '종단면도' 유추 문자열 혹은 특정 좌표계 활용
            if any(k in txt for k in ["종단면도", "횡단면도", "단면도"]) or ent.InsertionPoint[0] > 7000000:
                base_x = ent.InsertionPoint[0]
                base_y = ent.InsertionPoint[1]
                print(f"Detected Section Anchor Point: '{txt}' at X:{base_x:.2f}, Y:{base_y:.2f}")
                break
        except:
            continue
            
    ss.Clear()
    ss.Delete()
    
    if base_x is None or base_y is None:
        # 도출된 실 도면 좌표계 강제 보정 적용
        base_x, base_y = 7770158.66, 1200635.73
        print(f"Fallback to detected drawing absolute coordinates: X:{base_x:.2f}, Y:{base_y:.2f}")

    # 2. 지음건축 (Jieum Architects) 레이어 생성 (TXT)
    layer_name = "TXT"
    try:
        doc.Layers.Add(layer_name)
    except:
        pass
    
    # 3. AddLeader를 이용한 지시선타입의 작도 함수 정의
    def create_professional_leader(start_pt, land_pt, end_pt, text_content):
        try:
            # 3.1 MText 객체 우선 작성 (Leader의 Annotation 역할)
            v_end_pt = win32com.client.VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_R8, end_pt)
            mtext = ms.AddMText(v_end_pt, 0.0, text_content)
            mtext.Height = 350.0 # 지음건축 표준 축척 텍스트 크기
            mtext.Layer = layer_name
            mtext.Color = 4 # Cyan (지음 표준/XiCAD 지시선 호환색상)
            
            # 3.2 Leader의 PointsArray 설정 (시작점 -> 꺾임점 -> 끝점)
            pts = list(start_pt) + list(land_pt) + list(end_pt)
            v_pts = win32com.client.VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_R8, pts)
            
            # 3.3 AddLeader API 호출 (ZWCAD 정규 지시선 객체 생성)
            # 1 = acLineWithArrow (화살표 지시선)
            leader = ms.AddLeader(v_pts, mtext, 1)
            leader.Layer = layer_name
            leader.Color = 4
            
            # 3.4 지시선과 문자의 정렬 방향 자동 연동을 위해 텍스트 위치 보정
            print(f"Successfully created Leader & Annotation: '{text_content}'")
            return True
        except Exception as ex:
            print(f"Leader Creation Failed for '{text_content}': {ex}")
            # Fallback: 일반 라인 + 텍스트 작도
            try:
                v_start = win32com.client.VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_R8, start_pt)
                v_land = win32com.client.VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_R8, land_pt)
                v_end = win32com.client.VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_R8, end_pt)
                l1 = ms.AddLine(v_start, v_land)
                l2 = ms.AddLine(v_land, v_end)
                l1.Layer = layer_name
                l2.Layer = layer_name
                l1.Color = 4
                l2.Color = 4
                
                v_txt_pt = win32com.client.VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_R8, [end_pt[0] + 100, end_pt[1] + 100, end_pt[2]])
                txt = ms.AddText(text_content, v_txt_pt, 350.0)
                txt.Layer = layer_name
                txt.Color = 4
                print(f"Successfully created Fallback Line+Text: '{text_content}'")
                return True
            except Exception as e2:
                print(f"Fallback Creation Failed: {e2}")
                return False

    # 4. 실 지음건축 단열 및 마감 표준에 근거한 상대적 지시선 작도
    print("\n--- Drafting Professional Leaders ---")
    
    # 4.1 지붕 단열재 (T180 그라스울 판넬(지붕))
    # 앵커 대비 위쪽 및 지붕 빗각 지향
    p1_start = [base_x - 500, base_y + 7500, 0]
    p1_land = [base_x + 1000, base_y + 8200, 0]
    p1_end  = [base_x + 4000, base_y + 8200, 0]
    create_professional_leader(p1_start, p1_land, p1_end, "T180 그라스울 판넬(지붕)")

    # 4.2 벽체 단열재 (T100 그라스울 벽판넬)
    # 건물 좌측 외벽면 지향
    p2_start = [base_x - 3600, base_y + 3500, 0]
    p2_land = [base_x - 4800, base_y + 4000, 0]
    p2_end  = [base_x - 7800, base_y + 4000, 0]
    create_professional_leader(p2_start, p2_land, p2_end, "T100 그라스울 벽판넬")

    # 4.3 실내재료마감
    # 건물의 하단 내측 공간 지향
    p3_start = [base_x + 1500, base_y + 2000, 0]
    p3_land = [base_x + 3000, base_y + 1500, 0]
    p3_end  = [base_x + 6000, base_y + 1500, 0]
    create_professional_leader(p3_start, p3_land, p3_end, "실내재료마감")

    # 4.4 철골구조 부재 스펙 (H-300x150x6.5x9)
    # 기둥 및 프레임 구조물 접합부 지향
    p4_start = [base_x + 3000, base_y + 5500, 0]
    p4_land = [base_x + 4500, base_y + 6000, 0]
    p4_end  = [base_x + 7500, base_y + 6000, 0]
    create_professional_leader(p4_start, p4_land, p4_end, "H-300x150x6.5x9 (작은 보)")

    print("\n--- Drafting Process Completed! ---")

if __name__ == "__main__":
    draw_jieum_section_leaders()
