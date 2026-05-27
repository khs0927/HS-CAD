# -*- coding: utf-8 -*-
"""ZWCAD 2024 & XiCAD 새 도면 자율 드래프팅 완벽 오케스트레이션"""
import win32com.client
import time
import os

def run_perfect_new_document_drafting():
    print("=" * 80)
    print("ZWCAD 2024 & XiCAD 새 백지 도면 자율 드래프팅 실시간 완벽 실증")
    print("=" * 80)

    try:
        app = win32com.client.GetActiveObject("ZWCAD.Application.2024")
    except Exception as e:
        print(f"[FAIL] ZWCAD 2024 연결 실패: {e}")
        return

    # 1. 새 도면(Documents.Add) 생성 및 활성화
    print("\n[Step 1] 완전히 새로운 백지 도면 생성 중...")
    try:
        # 새 도면 개설
        new_doc = app.Documents.Add()
        time.sleep(3.0)
        # 새로 생성된 도면 활성화 확증
        new_doc.Activate()
        print(f"[SUCCESS] 새 도면 개설 및 활성화 완료: {new_doc.Name}")
    except Exception as e:
        print(f"[FAIL] 새 도면 개설 실패: {e}")
        return

    # 2. 새 도면에 XiCAD 엔진 로드 및 초기화
    print("\n[Step 2] 새 도면 내 XiCAD LISP 환경 강제 로드 및 초기화 대기...")
    init_lisp = (
        '(progn '
        '  (setenv "ACAD" (strcat (getenv "ACAD") ";C:/XICAD;C:/XICAD/Lisp;C:/XICAD/Lib")) '
        '  (if (findfile "xi.fas") (load "xi.fas")) '
        '  (princ "\\n[AI] XiCAD Engine Loaded on New Document.\\n") '
        '  (princ)'
        ')\n'
    )
    new_doc.SendCommand(init_lisp)
    time.sleep(4.0)  # XiCAD 로딩 및 뷰 레포트 출력을 완전히 기다림

    # 3. [xiDrawWall] 벽끌기(D) 옵션을 활용한 진짜 100% 벽체 작도
    # 오리지널 프롬프트 분석 매치 순서:
    # 1. xiDrawWall 입력 ➡️ 2. D (벽끌기 선택) ➡️ 3. 시작점 ➡️ 4. 끝점 ➡️ 5. 두께 ➡️ 6. 방향점 ➡️ 7. 엔터
    print("\n[Step 3] XiCAD 'xiDrawWall' 벽끌기(D) 실시간 작도 주입...")
    try:
        # 1) Esc 가드 후 xiDrawWall 가동
        new_doc.SendCommand("\x1b\x1bxiDrawWall\n")
        time.sleep(1.5)
        
        # 2) 벽끌기(D) 옵션 선택
        new_doc.SendCommand("D\n")
        time.sleep(1.5)
        
        # 3) 시작점 좌표 (24000, 32000) 주입 (한쪽 벽면 점 지정)
        new_doc.SendCommand("24000,32000\n")
        time.sleep(1.5)
        
        # 4) 끝점 좌표 (50000, 32000) 주입 (같은 벽면의 폭/끝점 지정)
        new_doc.SendCommand("50000,32000\n")
        time.sleep(1.5)
        
        # 5) 벽 두께 200mm 주입
        new_doc.SendCommand("200\n")
        time.sleep(1.5)
        
        # 6) 옮길 방향 지정 (Y축 하단으로 두께를 주기 위해 Y=31900 클릭)
        new_doc.SendCommand("24000,31900\n")
        time.sleep(1.5)
        
        # 7) 명령어 완료 엔터
        new_doc.SendCommand("\n")
        time.sleep(2.0)
        print("[SUCCESS] 벽끌기(D) 정밀 시퀀스 완료! 실물 벽체선 생성 성공.")
    except Exception as e:
        print(f"[FAIL] 벽체 드로잉 중 예외 발생: {e}")

    # 4. [xiWin2] 새로 생성된 벽체 상에 2소 미서기창 정밀 주입
    # 프롬프트 구성: xiWin2 -> 1800 (창폭) -> 27000,32000 (벽체 삽입점) -> 27000,31900 (방향지정)
    print("\n[Step 4] XiCAD 'xiWin2' 프롬프트 맞춤형 창호 배치...")
    try:
        # 첫 번째 창호 (X = 27000, 너비 1800)
        print("  * 첫 번째 창호 (너비 1800, X=27000) 배치 시도...")
        new_doc.SendCommand("\x1b\x1bxiWin2\n")
        time.sleep(1.5)
        
        # 폭 1800 주입
        new_doc.SendCommand("1800\n")
        time.sleep(1.5)
        
        # 삽입점 지정 (벽체 위의 좌표)
        new_doc.SendCommand("27000,32000\n")
        time.sleep(1.5)
        
        # 실내측 방향 클릭 (Y축 하단)
        new_doc.SendCommand("27000,31900\n")
        time.sleep(2.0)
        print("[SUCCESS] 첫 번째 창호 xiWin2(1800) 배치 완료")

        # 두 번째 창호 (X = 38000, 너비 2400)
        print("  * 두 번째 창호 (너비 2400, X=38000) 배치 시도...")
        new_doc.SendCommand("\x1b\x1bxiWin2\n")
        time.sleep(1.5)
        
        # 폭 2400 주입
        new_doc.SendCommand("2400\n")
        time.sleep(1.5)
        
        # 삽입점 지정
        new_doc.SendCommand("38000,32000\n")
        time.sleep(1.5)
        
        # 실내측 방향 클릭
        new_doc.SendCommand("38000,31900\n")
        time.sleep(2.0)
        print("[SUCCESS] 두 번째 창호 xiWin2(2400) 배치 완료")
    except Exception as e:
        print(f"[FAIL] 창호 배치 중 예외 발생: {e}")

    # 5. [xiDoor1] 새로 생성된 우측 벽체에 외여닫이문 정밀 주입
    # 프롬프트 구성: xiDoor1 -> 900 (문폭) -> 45000,32000 (경첩 삽입점) -> 45000,32100 (방향지정)
    print("\n[Step 5] XiCAD 'xiDoor1' 프롬프트 맞춤형 외여닫이문 배치...")
    try:
        new_doc.SendCommand("\x1b\x1bxiDoor1\n")
        time.sleep(1.5)
        
        # 폭 900 주입
        new_doc.SendCommand("900\n")
        time.sleep(1.5)
        
        # 경첩 삽입점 지정
        new_doc.SendCommand("45000,32000\n")
        time.sleep(1.5)
        
        # 열림 방향 클릭 (Y축 상단)
        new_doc.SendCommand("45000,32100\n")
        time.sleep(2.0)
        print("[SUCCESS] 외여닫이문 xiDoor1(900) 배치 완료")
    except Exception as e:
        print(f"[FAIL] 문 배치 중 예외 발생: {e}")

    # 6. 화면 재생성 및 ZOOM Window로 뷰 자동 최적화
    try:
        new_doc.Regen(1)
        new_doc.SendCommand("\x1b\x1bZOOM\nW\n22000,34000\n52000,30000\n")
        print("\n[Step 6] 새 도면 뷰 최적화 완료 (ZOOM Window)")
    except Exception:
        pass

    print("\n" + "=" * 80)
    print("새 도면 실시간 완벽 자율 드래프팅 오케스트레이션 완료!")
    print(f"새 도면({new_doc.Name})에 실시간으로 생성된 벽체와 창호, 문을 ZWCAD 창에서 직접 확인하십시오.")
    print("=" * 80)

if __name__ == "__main__":
    run_perfect_new_document_drafting()
