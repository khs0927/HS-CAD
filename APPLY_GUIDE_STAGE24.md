# HS-CAD Stage 24 적용 가이드

Stage 24는 Stage 23 이후 단계입니다.

## 목표

- image-to-CAD 결과 DXF를 style_context 기준으로 후처리합니다.
- preview insert 결과를 session으로 추적합니다.
- preview block을 삭제/교체할 수 있는 lifecycle manager를 추가합니다.
- QA markup과 low confidence review를 생성합니다.
- 원본 DWG 병합은 하지 않고 merge candidate plan만 생성합니다.

## 적용 방법

```powershell
git checkout stage-23-style-context-bridge
git checkout -b stage-24-preview-lifecycle
```

ZIP 안의 `src`, `docs`, `tests`를 HS-CAD 루트에 병합하세요.

## 테스트

PowerShell glob 문제를 피하려면:

```powershell
$files = Get-ChildItem tests\test_stage24_*.py | Select-Object -ExpandProperty FullName
python -m pytest @files
```

## 기본 명령

### DXF 후처리

```powershell
python -m src.dxf_style_rewriter.cli rewrite-dxf `
  --source-dxf outputs/demo/result_wallsolid.dxf `
  --styled-result generated/neuro_bridge/styled_result.json `
  --style-context generated/style_context/style_context.json `
  --out generated/stage24
```

### Preview session 생성

```powershell
python -m src.preview_lifecycle.cli create-session `
  --plan generated/neuro_bridge/preview_insert_plan.json `
  --insert-result generated/neuro_bridge/insert_preview_result.json `
  --out generated/stage24
```

### Preview 제거 dry-run

```powershell
python -m src.preview_lifecycle.cli remove-preview `
  --session generated/stage24/preview_session.json `
  --out generated/stage24
```

### QA 리포트

```powershell
python -m src.qa_visual_review.cli build-review `
  --styled-result generated/neuro_bridge/styled_result.json `
  --preview-session generated/stage24/preview_session.json `
  --out generated/stage24
```

### 병합 후보 계획

```powershell
python -m src.merge_planner.cli build-merge-candidate `
  --preview-session generated/stage24/preview_session.json `
  --style-context generated/style_context/style_context.json `
  --styled-result generated/neuro_bridge/styled_result.json `
  --out generated/stage24
```

## 실제 ZWCAD 실행

실제 제거/교체는 반드시 열린 ZWCAD 도면에서 `--allow-execute`를 붙여 실행하세요.

```powershell
python -m src.preview_lifecycle.cli remove-preview `
  --session generated/stage24/preview_session.json `
  --allow-execute `
  --out generated/stage24
```

안전장치:
- Save / SaveAs 호출 없음
- Purge 없음
- Explode 없음
- Block definition 수정 없음
- preview_session에 기록된 inserted_handle만 대상으로 함
