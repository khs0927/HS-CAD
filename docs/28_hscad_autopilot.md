# HS-CAD Autopilot

## 목적

사용자가 “자동으로 진행해줘”라고 요청했을 때, HS-CAD가 현재 작업 성격을 판단하고 안전한 단계들을 논스톱으로 수행하도록 합니다.

## 중요한 구분

| 구분 | 설명 |
|---|---|
| Safe Autopilot | 검사, 계획, 파일 생성, 리포트, 검증만 자동 수행 |
| Held Steps | 도면 수정/저장/삭제/폭파/실행이 필요한 단계는 보류 |
| Human Review | 보류 단계는 사람이 보고 승인해야 함 |

## 기본 안전 원칙

- 원본 DWG 저장 금지
- Delete/Purge/Explode 자동 실행 금지
- ZWCAD SendCommand 자동 실행 금지
- recipe_registry 자동 수정 금지
- verified/scriptable 자동 승격 금지

## 대표 명령

```powershell
python -m src.main hscad-auto "스캔 이미지 도면을 DXF로 만들고 XiCAD 계획까지 생성해줘" --has-image --synthetic --run-safe --out-dir outputs/autopilot

python -m src.main hscad-auto "XiCAD WAL,D1,W1 계약 검증 준비를 자동으로 진행해줘" --mode contract --aliases WAL,D1,W1,INS,COL,BE --run-safe --out-dir outputs/autopilot_contract
```

## 산출물

- `autopilot_plan.json`
- `autopilot_result.json`
- `autopilot_report.md`

## 다음 단계

Autopilot은 safe-only 흐름을 먼저 완성합니다.  
실제 ZWCAD 도면 적용은 별도 preview/save-as 기반 workflow로 분리해야 합니다.
