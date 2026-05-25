# HS-CAD Next Stage Overlay Plan

## 목적

이번 overlay는 기존 PR55 아키텍처 스켈레톤을 다음 수준으로 끌어올리기 위한 실행 코드입니다.

## 새로 강화되는 흐름

```text
Input DWG/DXF/PDF/Image
  ↓
fileizers
  ↓
FileizedDrawing + Evidence
  ↓
basic entity analysis
  ↓
EvidenceFusionResult
  ↓
DomainRuleResult(plan-only)
  ↓
result_centerline.dxf / result_wallsolid.dxf / qa_overlay.dxf
  ↓
NEXT_STAGE_PIPELINE_RESULT.json
```

## 포함 기능

- DXF fileizer: `ezdxf`가 있으면 실제 entity 추출, 없으면 최소 텍스트 기반 fallback
- DWG fileizer: ODAFC 변환 계획/실행 wrapper. 실패 시 COM scan 없이 evidence error 반환
- PDF/Image fileizer: optional dependency가 없어도 metadata evidence 반환
- Evidence model: source, confidence, audit trail, JSON serialization
- Fusion model: evidence를 source/kind/entity 기준으로 통합하고 conflict 후보 생성
- Domain rules: rule 결과는 `plan-only`. CAD 명령 실행 없음
- DXF builders: `ezdxf` 사용 가능 시 정식 DXF, 없으면 최소 ASCII DXF 생성
- Next stage pipeline CLI: end-to-end smoke 가능

## 안전 정책

```json
{
  "final_live_runner_implemented": false,
  "sendcommand_allowed_by_default": false,
  "cad_execution_allowed_by_default": false,
  "zwcad_com_allowed_by_default": false,
  "xicad_alias_execution_allowed_by_default": false
}
```
