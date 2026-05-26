# 04. Agent 2 – Local Implementation Direction

## 역할

Agent 2는 구현 담당이다. 단, 지금은 새 기능이 아니라 검증 하네스와 안전성 자동화 구현만 담당한다.

## 현재 우선순위

1. PR #111이 병합될 때까지 새 worker/CLI 등록 작업을 시작하지 않는다.
2. PR #111 병합 후 다음 브랜치를 만든다.

```text
audit/github-quality-gate-watch
```

## 다음 구현 후보

허용 파일:

```text
scripts/quality_gate_scan.py
scripts/watch_quality_gate.ps1
tests/test_quality_gate_scan.py
docs/quality_gate_watch.md
```

Agent 5와 조율 후 별도 PR에서 허용 가능:

```text
.github/workflows/quality-gate.yml
```

## 구현 원칙

- 정적 스캔, import 검증, `--help` 검증만 수행
- CAD 실행 없음
- worker 실제 실행 없음
- DWG/DXF/PDF 실제 변환 없음
- outputs 파일은 생성 가능하지만 커밋 금지

## 금지 파일

```text
src/main.py
config/worker_manifest.json
src/adapters/zwcad_com_adapter.py
src/converters/oda_file_converter.py
src/integrations/zwcad_live/**
src/analysis/final_live_runner.py
src/app/zwcad_live_runner_cli.py
```

## PR #105 관련

PR #105가 필요하다면 기존 PR을 고치지 말고 최신 main에서 새 브랜치로 재작성한다. 첫 단계는 source-only planner이며 `src/main.py` 직접 등록은 금지한다.
