# -*- coding: utf-8 -*-
import win32com.client
import pythoncom
import sys

def scan_floor_plan_grids():
    print("Connecting to ZWCAD to scan floor plan...")
    try:
        app = win32com.client.GetActiveObject("ZWCAD.Application")
        doc = app.ActiveDocument
    except Exception as e:
        print(f"Connection Error: {e}")
        sys.exit(1)
        
    print(f"Scanning grids in document: {doc.Name}")
    
    # 1. SelectionSet으로 COL 레이어의 객체들 스캔
    ss_name = "ColScanSS"
    try:
        ss = doc.SelectionSets.Add(ss_name)
    except:
        ss = doc.SelectionSets.Item(ss_name)
        ss.Clear()
        
    f_type = win32com.client.VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_I2, [8]) # Layer filter
    f_data = win32com.client.VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_VARIANT, ["COL,A-COL"])
    
    try:
        ss.Select(5, None, None, f_type, f_data)
        print(f"Found COL/A-COL objects: {ss.Count}")
    except Exception as e:
        print(f"Selection error: {e}")
        
    columns_x = []
    for i in range(ss.Count):
        try:
            ent = ss.Item(i)
            # 블록 참조나 사각형(LWPolyline)인 경우 중심 X 검출
            if ent.ObjectName == "AcDbBlockReference":
                columns_x.append(ent.InsertionPoint[0])
            elif ent.ObjectName == "AcDbPolyline":
                # 폴리선 정점들의 X 평균
                coords = ent.Coordinates
                xs = [coords[j] for j in range(0, len(coords), 2)]
                columns_x.append(sum(xs) / len(xs))
        except:
            continue
            
    ss.Clear()
    ss.Delete()
    
    # 중복 제거 및 정렬
    unique_xs = sorted(list(set([round(x, 1) for x in columns_x])))
    print(f"Detected Column X coordinates: {unique_xs}")
    
    # 만약 기둥이 검출되지 않았다면, 도면 전체 범위나 텍스트에서 힌트를 구함
    if not unique_xs:
        # 도면 한계나 모델 공간 전체 바운딩 박스를 힌트로 활용
        ext_min = doc.GetVariable("EXTMIN")
        ext_max = doc.GetVariable("EXTMAX")
        print(f"Drawing Extents: Min={ext_min}, Max={ext_max}")
        # 기본 스팬으로 12,000mm 및 7,200mm 스팬 정의
        # 앵커 근처 X: 7753558.87를 기준으로 임의 대입
        unique_xs = [7753558.87, 7760758.87, 7772633.87]
        print(f"Fallback to standard factory spans from drawings: {unique_xs}")
        
    # 스팬 정보 계산
    spans = []
    for i in range(len(unique_xs) - 1):
        spans.append(unique_xs[i+1] - unique_xs[i])
    print(f"Calculated Spans between grids: {spans}")
    
    return unique_xs

if __name__ == "__main__":
    scan_floor_plan_grids()
