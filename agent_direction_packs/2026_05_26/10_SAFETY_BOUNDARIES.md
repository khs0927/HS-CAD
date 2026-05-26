# 10. Safety Boundaries

## 전 에이전트 공통 금지

```text
CAD execution: NO
live runner production path: NO
original DWG mutation: NO
```

## 고위험 파일

```text
src/main.py
config/worker_manifest.json
src/adapters/zwcad_com_adapter.py
src/converters/oda_file_converter.py
src/integrations/zwcad_live/**
src/analysis/final_live_runner.py
src/app/zwcad_live_runner_cli.py
.github/workflows/*.yml
```

이 파일들은 명시된 전담 에이전트와 검증 하네스 없이 수정 금지다.

## 금지 artifacts

```text
outputs/**
artifacts/**
*.zip
*.dwg
*.dxf
*.sqlite
*.sqlite3
__pycache__/**
.pytest_cache/**
```

단, 로컬 outputs 보고서는 생성 가능하지만 커밋 금지다.

## 판단 등급

### PASS

- docs/tests/scripts only
- full pytest 통과
- src.main --help 통과
- artifact 없음
- high-risk 파일 없음

### REVIEW_REQUIRED

- docs-only이지만 stale 가능
- scripts/tests 추가이나 strict CI 전 단계
- CAD 관련 금지 키워드가 문서/도움말에만 등장

### BLOCKED

- full pytest 실패
- compileall 실패
- `src/main.py` 또는 `worker_manifest` 직접 변경
- live runner 파일 변경
- 실행 위험 코드
- artifact/binary 커밋
