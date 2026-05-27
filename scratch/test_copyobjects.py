# -*- coding: utf-8 -*-
"""ZWCAD COM CopyObjects API 테스트 스크립트"""
import win32com.client
import pythoncom
import sys

def test_copy():
    try:
        app = win32com.client.GetActiveObject("ZWCAD.Application.2024")
    except Exception as e:
        print(f"[FAIL] ZWCAD 연결 실패: {e}")
        return

    doc2 = None
    for doc in app.Documents:
        if "drawing2" in doc.Name.lower():
            doc2 = doc
            break
            
    if not doc2:
        print("[FAIL] Drawing2.dwg가 열려있지 않습니다.")
        return

    print(f"[OK] Source Drawing: {doc2.Name}")
    
    # 새 도면 만들기
    new_doc = app.Documents.Add("zwcad.dwt")
    print(f"[OK] Target Drawing: {new_doc.Name}")

    # CopyObjects 대상 수집 (나무 레이어 제외)
    objs_to_copy = []
    skipped_tree = 0
    
    for obj in doc2.ModelSpace:
        try:
            if obj.Layer.lower() == "@tree":
                skipped_tree += 1
                continue
            objs_to_copy.append(obj)
        except Exception:
            continue
            
    print(f"[OK] 복사할 객체 수: {len(objs_to_copy)} (나무 제외 {skipped_tree}개 생략)")

    if len(objs_to_copy) == 0:
        print("[FAIL] 복사할 객체가 없습니다.")
        return

    # win32com VARIANT 배열로 변환
    # ZWCAD의 CopyObjects는 IDispatch pointer 배열을 받는다.
    try:
        # win32com.client.VARIANT를 사용한 Dispatch 객체 배열 래핑
        # VT_ARRAY | VT_DISPATCH 형태로 전달해야 함.
        obj_variants = win32com.client.VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_DISPATCH, objs_to_copy)
        
        # CopyObjects(ObjectsArray, Owner, [IDPairs])
        # ZWCAD의 Document 객체 또는 Database 객체에 CopyObjects 메소드가 존재함.
        # ZWCAD Database 또는 Document.CopyObjects 호출
        copied = doc2.CopyObjects(obj_variants, new_doc.ModelSpace)
        print(f"[SUCCESS] CopyObjects 성공! 복제된 객체 수: {len(copied)}")
        
        new_doc.Regen(1)
        new_doc.SaveAs(r"C:\cad\replicated_drawing2_copyobjects.dwg")
        print("[SUCCESS] 파일 저장 완료: C:\\cad\\replicated_drawing2_copyobjects.dwg")
    except Exception as e:
        print(f"[FAIL] CopyObjects 오류 발생: {e}")

if __name__ == "__main__":
    test_copy()
