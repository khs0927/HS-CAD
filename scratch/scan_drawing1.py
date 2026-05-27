# -*- coding: utf-8 -*-
"""Drawing1.dwg 정밀 가이드라인 및 레이아웃 스캐너"""
import win32com.client
from collections import defaultdict
import os

def scan_drawing1():
    print("=" * 80)
    print("ZWCAD 2024 - Drawing1.dwg 가이드선 & 레이아웃 좌표 정밀 스캔")
    print("=" * 80)

    try:
        app = win32com.client.GetActiveObject("ZWCAD.Application.2024")
    except Exception as e:
        print(f"[FAIL] ZWCAD 연결 실패: {e}")
        return

    doc1 = None
    for doc in app.Documents:
        if "drawing1" in doc.Name.lower():
            doc1 = doc
            break
            
    if not doc1:
        print("[FAIL] Drawing1.dwg가 ZWCAD에 열려있지 않습니다.")
        print(f"현재 열린 도면들: {[d.Name for d in app.Documents]}")
        return

    print(f"[SUCCESS] 대상 도면 발견: {doc1.Name}")
    ms = doc1.ModelSpace
    total = ms.Count
    print(f"ModelSpace 총 객체 수: {total}")

    # 가이드 역할을 하는 레이어 정보 수집 (CEN, Defpoints, A-GRID 등)
    # 벽체(WAL)나 창문(WIN) 좌표를 추출해서 AI가 작도할 수 있는 베이스 맵 구성
    guide_lines = []
    win_doors = []
    other_guides = []
    
    for idx in range(total):
        try:
            obj = ms.Item(idx)
            layer = str(obj.Layer).upper()
            etype = obj.EntityName
            
            # 중심선(CEN, CEN2, A-GRID) 또는 벽체선(WAL, A-WALL)
            if "CEN" in layer or "GRID" in layer or "WAL" in layer:
                if etype == "AcDbLine":
                    guide_lines.append({
                        "id": idx,
                        "layer": layer,
                        "start": [round(x, 2) for x in obj.StartPoint],
                        "end": [round(x, 2) for x in obj.EndPoint]
                    })
                elif etype in ("AcDbPolyline", "AcDb2dPolyline"):
                    guide_lines.append({
                        "id": idx,
                        "layer": layer,
                        "coords": [round(x, 2) for x in obj.Coordinates]
                    })
            elif "WIN" in layer or "DOOR" in layer:
                # 창문과 문 객체들의 위치를 수집하여 훗곳에 W1, W2, D1, D2를 올릴 자리 파악
                if etype == "AcDbBlockReference":
                    win_doors.append({
                        "id": idx,
                        "layer": layer,
                        "name": obj.Name,
                        "insert": [round(x, 2) for x in obj.InsertionPoint],
                        "scale": [round(obj.XScaleFactor, 2), round(obj.YScaleFactor, 2)]
                    })
                elif etype == "AcDbLine":
                    win_doors.append({
                        "id": idx,
                        "layer": layer,
                        "start": [round(x, 2) for x in obj.StartPoint],
                        "end": [round(x, 2) for x in obj.EndPoint]
                    })
        except Exception:
            continue

    print(f"\n[분석 결과] 가이드선 개수: {len(guide_lines)}개")
    print(f"[분석 결과] 창호/문 관련 개체: {len(win_doors)}개")
    
    print("\n--- 가이드선 샘플 (상위 15개) ---")
    for g in guide_lines[:15]:
        if "start" in g:
            print(f"  [{g['layer']}] Line ID: {g['id']} | Start: {g['start']} -> End: {g['end']}")
        else:
            print(f"  [{g['layer']}] Polyline ID: {g['id']} | Coords: {g['coords']}")
            
    print("\n--- 창호/문 객체 샘플 (상위 15개) ---")
    for wd in win_doors[:15]:
        if "name" in wd:
            print(f"  [{wd['layer']}] Block '{wd['name']}' ID: {wd['id']} | Insert: {wd['insert']} | Scale: {wd['scale']}")
        else:
            print(f"  [{wd['layer']}] Line ID: {wd['id']} | Start: {wd['start']} -> End: {wd['end']}")

if __name__ == "__main__":
    scan_drawing1()
