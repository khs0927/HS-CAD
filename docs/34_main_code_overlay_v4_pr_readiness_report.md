# HS-CAD Main-Code Overlay v4 PR Readiness Report

## 목적

v1/v2/v3에서 검증된 main-code pipeline, runtime fixture factory, evidence bridge를 실제 PR 후보로 정리하기 위한 준비 패치다.

## v4 범위

- Review-only command registry 추가
- Standalone review CLI 추가
- `src/main.py` patch script 추가
- Runtime artifact cleaner 추가
- Commit candidate filter 추가
- PR hygiene tests 추가

## 안전 원칙

v4는 다음을 수행하지 않는다.

- CAD 실행
- ZWCAD COM 호출
- AutoCAD SendCommand 호출
- XiCAD alias 실행
- 원본 DWG 변경
- output artifact 커밋

## 권장 적용 순서

1. v4 overlay dry-run
2. v4 overlay 실제 적용
3. targeted tests
4. standalone CLI smoke
5. `src/main.py` registration dry-run
6. 필요 시 `--apply`
7. full pytest
8. commit candidate filter
9. runtime artifact cleanup dry-run
10. commit 대상만 stage

## 커밋 제외 대상

- `_incoming/**`
- `outputs/**`
- `__pycache__/**`
- `.pytest_cache/**`
- `*.zip`
- `*.dwg`
- runtime `*.dxf`

## 다음 단계

v4 검증 후에는 두 갈래가 가능하다.

1. **PR 후보 정리**
   - v1/v2/v3/v4를 하나의 clean PR로 정리한다.
   - runtime artifact 제거 후 코드와 문서, 테스트만 포함한다.

2. **기존 analyzer와 실제 연결 강화**
   - 기존 exporter가 생성한 artifact schema 샘플을 golden fixture로 고정한다.
   - legacy adapter의 heuristic mapping을 schema-aware mapping으로 강화한다.
