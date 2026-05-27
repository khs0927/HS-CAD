# -*- coding: utf-8 -*-
"""ZWCAD COM CopyObjects 개별 객체 단위 복사 테스트"""
import win32com.client
import pythoncom
import sys

def test_individual_copy():
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

    # 새 도면 만들기
    new_doc = app.Documents.Add("zwcad.dwt")
    print(f"[OK] Target Drawing: {new_doc.Name}")

    # 테스트로 첫 5개 객체를 개별 CopyObjects로 복사해보기
    count = 0
    copied_count = 0
    
    for obj in doc2.ModelSpace:
        if obj.Layer.lower() == "@tree":
            continue
            
        try:
            # 1개짜리 Dispatch VARIANT 생성
            single_arr = win32com.client.VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_DISPATCH, [obj])
            copied = doc2.CopyObjects(single_arr, new_doc.ModelSpace)
            if len(copied) > 0:
                copied_count += 1
            count += 1
            if count >= 10:
                break
        except Exception as e:
            print(f"  [ERR] Index {count} 복사 실패: {e}")
            count += 1

    print(f"[OK] 시도한 객체: {count}개, 성공한 객체: {copied_count}개")
    new_doc.Close(False)

if __name__ == "__main__":
    test_individual_copy()
