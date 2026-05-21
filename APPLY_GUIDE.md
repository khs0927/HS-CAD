# HS-CAD Stage 23: Style Context Bridge + Neuro CAD Preview Insert

이 ZIP은 기존 HS-CAD 본체를 덮어쓰지 않고, 충돌을 줄이기 위해 **신규 모듈 중심**으로 구성했습니다.

## 포함 범위

- `src/hs_style_context/`
  - 기존 도면 문법 샘플 JSON들을 하나의 `style_context.json`으로 통합합니다.
- `src/neuro_seq_cad_bridge/`
  - `neuro_seq_cad`의 `result.json`과 DXF 결과를 HS-CAD style context에 맞춰 preview plan으로 변환합니다.
- `docs/22_style_context_bridge.md`
  - 전체 워크플로우 문서.
- `tests/test_stage23_*.py`
  - ZWCAD 없이 동작하는 단위 테스트.
- `tools/sample_style_near_handle_limited.py`
  - 기존 도구를 덮어쓰지 않는 성능 제한 버전 예시.
- `PYPROJECT_OPTIONAL_DEPS_SNIPPET.toml`
  - 필요 시 `pyproject.toml`에 수동 병합할 optional dependency/pytest marker 스니펫.

## 적용 방법

저장소 루트에서 압축을 푼 뒤 파일을 복사하세요.

```powershell
# 저장소 루트에서
Expand-Archive HS-CAD-stage23-style-context-bridge.zip -DestinationPath .
# 내부 폴더의 src/docs/tests/tools를 HS-CAD 루트에 병합
```

또는 압축 안의 `src`, `docs`, `tests`, `tools` 폴더를 HS-CAD 루트로 직접 복사해도 됩니다.

## 기본 실행

### 1. Style Context 생성

```powershell
python -m src.hs_style_context.builder --out generated/style_context
```

또는 브리지 CLI:

```powershell
python -m src.neuro_seq_cad_bridge.cli build-style-context --out generated/style_context
```

### 2. Neuro result를 스타일 적용 결과로 변환

```powershell
python -m src.neuro_seq_cad_bridge.cli adapt-neuro-result ^
  --result outputs/demo/result.json ^
  --style-context generated/style_context/style_context.json ^
  --out generated/neuro_bridge
```

파일이 없어도 dry-run warning을 남기고 안전하게 진행하도록 설계했습니다.

### 3. Preview Insert Plan 생성

```powershell
python -m src.neuro_seq_cad_bridge.cli build-preview-plan ^
  --styled-result generated/neuro_bridge/styled_result.json ^
  --centerline-dxf outputs/demo/result_centerline.dxf ^
  --wallsolid-dxf outputs/demo/result_wallsolid.dxf ^
  --style-context generated/style_context/style_context.json ^
  --out generated/neuro_bridge
```

### 4. 전체 dry-run 계획 생성

```powershell
python -m src.neuro_seq_cad_bridge.cli run-all-preview-plan ^
  --result outputs/demo/result.json ^
  --centerline-dxf outputs/demo/result_centerline.dxf ^
  --wallsolid-dxf outputs/demo/result_wallsolid.dxf ^
  --out generated/neuro_bridge
```

### 5. 실제 ZWCAD preview insert

```powershell
python -m src.neuro_seq_cad_bridge.cli insert-preview ^
  --plan generated/neuro_bridge/preview_insert_plan.json ^
  --allow-execute ^
  --out generated/neuro_bridge
```

주의: 이 명령도 Save/SaveAs를 호출하지 않습니다. 삽입 전 UNDO MARK를 만들고, block reference layer는 기본 `QA-REVIEW`입니다.

되돌리기:

```powershell
python -m src.neuro_seq_cad_bridge.cli undo-preview
```

## 테스트

일반 테스트:

```powershell
python -m pytest tests/test_stage23_*.py
```

실제 ZWCAD 테스트는 이 ZIP에 기본 포함하지 않았습니다. 실환경 테스트는 별도 `integration` marker로 추가하세요.

## 충돌 방지 기준

- 기존 `src.main`, `src/adapters`, `src/extensions/xicad_safe_bridge`를 수정하지 않습니다.
- 기존 DWG 레이어를 자동 리맵하지 않습니다.
- 기존 DWG에 직접 Save/SaveAs/Purge/Delete/Explode를 수행하지 않습니다.
- 이미지→CAD 결과는 preview plan 또는 block insert preview로만 연결합니다.
