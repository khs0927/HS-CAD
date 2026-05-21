# 22. Style Context Bridge

## Purpose

`Style Context Bridge`는 `neuro_seq_cad`가 만든 이미지/PDF→CAD 결과를 HS-CAD의 기존 도면 문법 학습 흐름과 연결하는 격리 레이어입니다.

이 모듈의 목적은 기존 DWG를 직접 수정하는 것이 아닙니다.

```text
이미지/PDF → neuro_seq_cad result.json / DXF
기존 DWG → local style / sheet grammar / active scan
두 정보를 연결 → preview_insert_plan.json
ZWCAD 활성 도면 → 저장 없이 block preview 삽입
```

## Core Safety Rules

- 기존 DWG 레이어를 자동 리맵하지 않습니다.
- 기존 객체를 수정하지 않습니다.
- Save / SaveAs를 호출하지 않습니다.
- Purge / Delete / Explode를 수행하지 않습니다.
- Block definition 내부를 수정하지 않습니다.
- 실제 삽입은 `--allow-execute`가 있을 때만 수행합니다.
- 삽입 전 UNDO MARK를 만들고, 실패해도 저장하지 않습니다.
- preview block reference layer는 기본 `QA-REVIEW`입니다.

## Style Context Priority

스타일 결정 우선순위는 다음과 같습니다.

1. 사용자가 명시한 스타일
2. `local_style_sample.json`
3. `zium_sheet_usable_area.json`
4. `active_form_sample.json`
5. `active_scan.json`
6. `neuro_seq_cad result.json`의 confidence/provenance
7. `drawing_standards.py` 기본값
8. `QA-REVIEW` fallback

## Main Files

```text
src/hs_style_context/
  schema.py
  loader.py
  builder.py
  resolver.py
  report.py

src/neuro_seq_cad_bridge/
  result_loader.py
  style_adapter.py
  cadpatch_builder.py
  preview_insert.py
  qa_merger.py
  cli.py
```

## CLI Examples

### Build Style Context

```bash
python -m src.neuro_seq_cad_bridge.cli build-style-context \
  --local-style outputs/style_sample_current/local_style_sample.json \
  --zium-sheet outputs/zium_sheet_area_current/zium_sheet_usable_area.json \
  --active-form outputs/active_form_analysis_current/active_form_sample.json \
  --active-scan outputs/active_scan_current/active_scan.json \
  --out generated/style_context
```

### Adapt Neuro Result

```bash
python -m src.neuro_seq_cad_bridge.cli adapt-neuro-result \
  --result outputs/demo/result.json \
  --style-context generated/style_context/style_context.json \
  --out generated/neuro_bridge
```

### Build Preview Plan

```bash
python -m src.neuro_seq_cad_bridge.cli build-preview-plan \
  --styled-result generated/neuro_bridge/styled_result.json \
  --centerline-dxf outputs/demo/result_centerline.dxf \
  --wallsolid-dxf outputs/demo/result_wallsolid.dxf \
  --style-context generated/style_context/style_context.json \
  --out generated/neuro_bridge
```

### Run All Dry-Run Plan

```bash
python -m src.neuro_seq_cad_bridge.cli run-all-preview-plan \
  --result outputs/demo/result.json \
  --centerline-dxf outputs/demo/result_centerline.dxf \
  --wallsolid-dxf outputs/demo/result_wallsolid.dxf \
  --out generated/neuro_bridge
```

파일이 없어도 명령은 실패하지 않고 warning을 기록합니다.

### Insert Preview Into Active ZWCAD

```bash
python -m src.neuro_seq_cad_bridge.cli insert-preview \
  --plan generated/neuro_bridge/preview_insert_plan.json \
  --allow-execute \
  --out generated/neuro_bridge
```

이 명령은 실제 ZWCAD 활성 도면이 필요합니다.

### Undo Preview

```bash
python -m src.neuro_seq_cad_bridge.cli undo-preview
```

## Standalone vs Existing DWG Preview

### `standalone_dxf`

- `WAL_HATCH`, `RAW_LINES`, `AI_LOWCONF`, `QA_MARKUP` 등 image-to-CAD 생성 레이어를 사용할 수 있습니다.
- 독립 DXF 결과물에 적합합니다.

### `existing_dwg_preview`

- 기존 사무소 DWG의 레이어를 직접 변경하지 않습니다.
- 변환 결과는 block preview로 격리합니다.
- raw/low confidence 요소는 `QA-REVIEW` 또는 `AI_LOWCONF`로 남겨 검수합니다.

## Integration Testing

실제 ZWCAD가 필요한 테스트는 일반 pytest에서 제외해야 합니다.

```bash
set HS_CAD_RUN_ZWCAD_TESTS=1
python -m pytest -m integration
```

## Outputs

```text
generated/style_context/style_context.json
generated/style_context/style_context.md
generated/neuro_bridge/styled_result.json
generated/neuro_bridge/styled_result.md
generated/neuro_bridge/preview_insert_plan.json
generated/neuro_bridge/preview_insert_plan.md
generated/neuro_bridge/merged_qa_report.md
```
