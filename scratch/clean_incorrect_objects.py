# -*- coding: utf-8 -*-
import win32com.client
import pythoncom
import sys

def clean_incorrect_objects():
    print("Connecting to ZWCAD for cleaning...")
    try:
        app = win32com.client.GetActiveObject("ZWCAD.Application")
    except Exception as e:
        print(f"Connection error: {e}")
        sys.exit(1)
        
    # 모든 열려있는 문서에 대해 청소 수행 (포커스 꼬임 방지)
    for doc_idx in range(app.Documents.Count):
        doc = app.Documents.Item(doc_idx)
        print(f"\nScanning document: {doc.Name}")
        ms = doc.ModelSpace
        
        delete_count = 0
        
        # 삭제할 키워드 목록
        keywords = [
            "T180 그라스울", 
            "T100 그라스울", 
            "실내재료마감", 
            "Rigid Urethane", 
            "XiCAD 표준", 
            "ArchiOffice 표준"
        ]
        
        # 안전한 순회를 위해 역순으로 검사 및 삭제
        for i in range(ms.Count - 1, -1, -1):
            try:
                ent = ms.Item(i)
                name = ent.ObjectName
                
                # 1. 텍스트 및 다행텍스트 검사
                if name in ["AcDbText", "AcDbMText"]:
                    txt = ent.TextString
                    if any(kw in txt for kw in keywords):
                        print(f"Deleting text: '{txt}' at ({ent.InsertionPoint[0]:.2f}, {ent.InsertionPoint[1]:.2f})")
                        ent.Delete()
                        delete_count += 1
                        
                # 2. 지시선(Leader) 객체 검사
                elif name == "AcDbLeader":
                    # 지시선에 연결된 Annotation 객체가 우리가 만든 것인지 확인하거나, 
                    # 또는 지시선 자체의 좌표 범위가 엉뚱한 곳에 있는 경우 (예: X: 215762 또는 X: 7770158 등) 삭제
                    # 안전을 위해 우리가 그린 레이어 "TXT" 또는 "A-ANNO-TEXT" 상의 Leader 삭제
                    if ent.Layer in ["TXT", "A-ANNO-TEXT"]:
                        print(f"Deleting Leader object on layer {ent.Layer}")
                        ent.Delete()
                        delete_count += 1
                        
                # 3. 일반 라인 검사 (레이어가 A-ANNO-TEXT 이거나 TXT 인 지시선용 라인)
                elif name == "AcDbLine":
                    if ent.Layer in ["TXT", "A-ANNO-TEXT"]:
                        # 엉뚱한 좌표 영역의 라인 삭제
                        xs, ys = ent.StartPoint[0], ent.StartPoint[1]
                        if xs < 300000 or xs > 7000000:
                            print(f"Deleting incorrect line on layer {ent.Layer}")
                            ent.Delete()
                            delete_count += 1
            except Exception as ex:
                continue
                
        print(f"Cleaned {delete_count} incorrect objects from {doc.Name}")
        doc.Regen(1)

if __name__ == "__main__":
    clean_incorrect_objects()
