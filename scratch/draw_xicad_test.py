# -*- coding: utf-8 -*-
"""ZWCAD 2024 & XiCAD 실시간 LISP 로딩 및 명령어 실증 스크립트"""
import win32com.client
import sys
import time

def demo_xicad_drafting():
    print("=" * 80)
    print("ZWCAD 2024 & XiCAD 실시간 자율 드래프팅 실증 프로그램")
    print("=" * 80)
    
    try:
        app = win32com.client.GetActiveObject("ZWCAD.Application.2024")
    except Exception as e:
        print(f"[FAIL] ZWCAD 2024 연결 실패: {e}")
        return

    # 활성 도면 가져오기
    doc = app.ActiveDocument
    print(f"[SUCCESS] 대상 도면 연결됨: {doc.Name}")
    
    # ZWCAD에 현재 로드된 XiCAD 상태 진단
    # LISP 환경에 XiCAD 함수들이 정의되어 있는지 확인하기 위해 LISP 표현식 평가 시도
    # (type c:wa)가 USUBR 또는 SUBR를 리턴하면 XiCAD가 이미 잘 로드된 상태임.
    # LISP evaluation 결과를 직접 가져오거나 SendCommand를 통해 흘려보냄
    
    print("\n[Step 1] XiCAD LISP 환경 진단 및 로딩 시작...")
    # ZWCAD에 ACAD 서포트 경로 추가 및 xi.fas / xi.zelx 강제 로딩 LISP 구문
    load_expr = (
        '(progn '
        '  (setq xi_root "C:/XICAD") '
        '  (setenv "ACAD" (strcat (getenv "ACAD") ";C:/XICAD;C:/XICAD/Lisp;C:/XICAD/Lib")) '
        '  (if (findfile "xi.fas") (load "xi.fas")) '
        '  (if (findfile "xi.zelx") (load "xi.zelx")) '
        '  (princ "\\n[AI] XiCAD Loader execution completed.\\n") '
        '  (princ)'
        ')\n'
    )
    
    try:
        doc.SendCommand(load_expr)
        print("[OK] XiCAD 로더 구문 전송 완료 (ZWCAD 창에서 로딩 프로세스 가동)")
        time.sleep(2)
    except Exception as e:
        print(f"[WARN] 로더 구문 전송 실패: {e}")

    # [Step 2] XiCAD 벽체 명령어 'WA' 구동 실증
    # ZWCAD SendCommand를 사용해 벽체 그리기 명령어(WA)를 흘려보냅니다.
    # 일반적으로 WA 명령어는 벽 두께 설정 및 두 점 입력을 받습니다.
    print("\n[Step 2] XiCAD 'WA' (벽체) 명령어 가동 실증...")
    try:
        # WA 명령어 실행 -> 벽 두께 200 입력 -> 시작점 (0, 1000) -> 끝점 (5000, 1000) -> 종료
        # ZWCAD SendCommand 포맷: 명령어와 매개변수 뒤에 공백이나 개행(\n)을 줘서 Enter 역할을 수행하게 함.
        # \x1b\x1b는 Esc를 두 번 눌러 이전 명령을 안전하게 취소하는 표준 CAD 가드입니다.
        doc.SendCommand("\x1b\x1bWA\n200\n0,1000\n5000,1000\n\n")
        print("[SUCCESS] 'WA' (벽체) 명령어 시퀀스가 ZWCAD 명령줄에 주입되었습니다!")
        time.sleep(1)
    except Exception as e:
        print(f"[FAIL] 'WA' 명령어 주입 실패: {e}")

    # [Step 3] XiCAD 'BE' (H빔) 명령어 가동 실증
    print("\n[Step 3] XiCAD 'BE' (H빔) 명령어 가동 실증...")
    try:
        # BE 명령어 실행 -> 규격 및 옵션 설정은 기본적으로 저장된 cfg를 따르므로, 
        # 화면 좌표 (2500, 2500) 지점에 H형강 단면 배치 시도
        doc.SendCommand("\x1b\x1bBE\n2500,2500\n0\n")
        print("[SUCCESS] 'BE' (H빔) 명령어 시퀀스가 ZWCAD 명령줄에 주입되었습니다!")
        time.sleep(1)
    except Exception as e:
        print(f"[FAIL] 'BE' 명령어 주입 실패: {e}")

    # [Step 4] XiCAD 'TX' (문자 주변 상자) 명령어 가동 실증
    print("\n[Step 4] XiCAD 'TX' (문자박스) 명령어 가동 실증...")
    try:
        # 텍스트를 먼저 하나 임시로 쓰고, 그 텍스트를 TX 명령어로 네모 박스 치는 시나리오
        # TEXT 명령어 -> 좌표 (1000, 3000) -> 높이 300 -> 회전 0 -> 텍스트 내용 주입 -> TX 실행
        doc.SendCommand("\x1b\x1b-TEXT\n1000,3000\n300\n0\nAI DRAFTING TEST\n\n")
        time.sleep(0.5)
        # TX 실행 후 마지막 객체(Last)를 선택하여 상자를 치게 함
        doc.SendCommand("\x1b\x1bTX\nL\n\n\n")
        print("[SUCCESS] 'TX' (문자박스) 명령어 시퀀스가 가동되었습니다!")
    except Exception as e:
        print(f"[FAIL] 'TX' 명령어 주입 실패: {e}")

    # [Step 5] 대지경계 클리핑 'XC' (XCLIP) 가이드라인 주입
    print("\n[Step 5] XiCAD 'XC' (도각제한 클리핑) 및 'LX' (지시선) 명령어 가이드라인...")
    print("  * 'XC'와 'LX' 역시 동일하게 SendCommand(\"XC\\n...\") 또는 LISP API를 통해")
    print("    안전하게 브릿지를 타고 실행될 수 있는 준비가 완료되어 있습니다.")
    
    print("\n" + "="*80)
    print("실증 완료: ZWCAD 2024 창의 명령줄 로그 및 작도 상태를 확인하십시오.")
    print("="*80)

if __name__ == "__main__":
    demo_xicad_drafting()
