import win32com.client
import sys
from pathlib import Path
sys.path.insert(0, str(Path(".").resolve()))
from src.adapters.zwcad_com_adapter import ZWCADCOMAdapter
from src.modifiers.architectural_modifier import draft_section_details, execute_planned_actions

def main():
    try:
        adapter = ZWCADCOMAdapter()
        adapter.connect()
        doc = adapter.doc or adapter.get_active_document()
        
        # Bring ZWCAD to front (optional)
        try:
            adapter.app.Visible = True
        except:
            pass
            
        print("사용자 입력을 대기 중입니다... ZWCAD 화면에서 단면도의 기준점(예: 지붕 상단)을 클릭하세요.")
        # 사용자에게 클릭 유도
        pt = doc.Utility.GetPoint(Prompt="\n단면도의 기준점을 클릭하세요 (십자선 위치): ")
        
        base_x, base_y = pt[0], pt[1]
        print(f"기준점 선택 완료: X={base_x:.1f}, Y={base_y:.1f}")
        
        # 작도 실행 (표준 레이어 적용된 최신 로직)
        actions = draft_section_details(base_x, base_y)
        res = execute_planned_actions(adapter, actions)
        
        print(f"작도 완료! 생성된 객체 수: {res.get('created')}")
        
    except Exception as e:
        print(f"오류 발생: {e}")

if __name__ == "__main__":
    main()
