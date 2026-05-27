# -*- coding: utf-8 -*-
"""replicated_drawing2_corrected.dwg 누락 요소 검증 스캔"""
import win32com.client
import pythoncom
from collections import defaultdict
import os

def scan_replicated():
    app = win32com.client.GetActiveObject('ZWCAD.Application.2024')
    doc_path = r"c:\cad\HS-CAD-clone\outputs\replicated_drawing2_corrected_1779905667.dwg"
    
    if not os.path.exists(doc_path):
        print(f"[ERROR] 복제 파일이 존재하지 않습니다: {doc_path}")
        return
        
    doc = None
    # 열려있는 문서 확인
    for i in range(app.Documents.Count):
        d = app.Documents.Item(i)
        if 'replicated_drawing2_corrected_1779905667' in d.Name.lower():
            doc = d
            break
            
    if not doc:
        print(f"[INFO] 복제 파일을 오픈합니다: {doc_path}")
        try:
            doc = app.Documents.Open(doc_path)
        except Exception as e:
            print(f"[ERROR] 파일 오픈 실패: {e}")
            return
            
    print(f"[OK] Scanning Replicated: {doc.Name}")
    ms = doc.ModelSpace
    total = ms.Count
    
    # Collectors
    linetypes = defaultdict(int)
    layers = defaultdict(lambda: {"count": 0, "color": None, "linetype": None})
    leaders = []
    dimensions = []
    hatches = []
    skipped_tree = 0
    entity_types = defaultdict(int)
    
    for idx in range(total):
        try:
            ent = ms.Item(idx)
        except:
            continue
            
        etype = ent.EntityName
        entity_types[etype] += 1
        
        # 레이어
        try:
            layer_name = ent.Layer
            layers[layer_name]["count"] += 1
            if layer_name.lower() == "@tree":
                skipped_tree += 1
        except:
            pass
            
        # 선종류
        try:
            lt = ent.Linetype
            linetypes[lt] += 1
        except:
            pass
            
        # 지시선
        if 'Leader' in etype:
            leaders.append(etype)
            
        # 치수
        if 'Dimension' in etype or 'Dim' in etype:
            dimensions.append(etype)
            
        # 해치
        if 'Hatch' in etype:
            hatches.append(etype)

    print("\n" + "="*70)
    print("복제본(replicated_drawing2_corrected.dwg) 정밀 스캔 결과")
    print("="*70)
    print(f"총 개체 수: {total} (원본 879개 중 @tree 34개 제외한 845개 타겟)")
    
    print("\n--- 개체 유형별 분포 ---")
    for k, v in sorted(entity_types.items(), key=lambda x: -x[1]):
        print(f"  {k}: {v}")
        
    print("\n--- 선종류(Linetype) 분포 ---")
    for lt, cnt in sorted(linetypes.items(), key=lambda x: -x[1]):
        print(f"  {lt}: {cnt}개")
        
    print(f"\n--- 지시선 (Leader) 개수: {len(leaders)}개 (원본 13개) ---")
    print(f"--- 치수 (Dimension) 개수: {len(dimensions)}개 (원본 38개) ---")
    print(f"--- 해치 (Hatch) 개수: {len(hatches)}개 (원본 3개) ---")
    print(f"--- 발견된 @tree 레이어 개체 개수: {skipped_tree}개 (0개여야 함) ---")

    print("\n--- 레이어 및 색상/선종류 설정 검증 (상위 15개) ---")
    try:
        lt_table = doc.Layers
        for i in range(min(15, lt_table.Count)):
            ly = lt_table.Item(i)
            print(f"  [{ly.Name}] Color={ly.Color}, Linetype={ly.Linetype}, On={ly.LayerOn}")
    except Exception as e:
        print(f"  레이어 테이블 스캔 실패: {e}")

if __name__ == "__main__":
    scan_replicated()
