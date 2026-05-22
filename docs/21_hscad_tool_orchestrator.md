# HS-CAD Tool Orchestrator

HS-CAD Tool Orchestrator는 HS-CAD 안에 있는 여러 도구를 빠트리지 않고 선택하기 위한 계획 전용 레이어입니다.

## 포함된 도구군

- DWG 검사: 객체, 레이어, 블록, 문자, 건축 감사, 수량
- 도면 표준: XiCAD 프로필, XiCAD 카탈로그, XiCAD Safe Bridge
- 이미지 도면화: floorplan-analyze, neuro_seq_cad analyze
- 변경 전 검토: run-command dry-run, xicad-safe-plan
- 보류형 실행 단계: 명시적 검토와 SaveAs가 필요한 작업
- 설정: third_party 준비, Raster2Seq 체크포인트 준비

## 새 명령

```powershell
python -m src.main hscad-tools
python -m src.main hscad-tools --query floorplan
python -m src.main hscad-tool-plan "스캔 이미지 도면을 DXF로 만들어줘" --has-image
python -m src.main hscad-tool-plan "기존 DWG의 레이어와 블록을 검토해줘" --has-dwg
python -m src.main hscad-tool-plan "기존 DWG를 수정해야 해" --has-dwg --wants-write
```

## 산출물

`hscad-tool-plan`은 기본적으로 아래 파일을 만듭니다.

- `outputs/tool_plan/hscad_tool_workflow_plan.json`
- `outputs/tool_plan/hscad_tool_workflow_plan.md`

## 안전 원칙

이 기능은 계획 전용입니다. 도면을 직접 열거나 저장하거나 수정하지 않습니다. 실제 도면 변경이 필요한 단계는 review-gated로 표시하고, 기존 HS-CAD의 dry-run과 SaveAs 흐름을 따르게 합니다.
