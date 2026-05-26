# 08. Agent 6 – Live Runner / ODA Policy Direction

## 역할

Agent 6은 구현자가 아니라 boundary/policy reviewer다.

## 현재 정책

- PR #69 FinalLiveRunner: HOLD
- PR #105 Execution Candidate Planner: 그대로 merge 금지, recreate 필요
- PR #82: closed / superseded / direct merge 금지
- Live CAD execution: NO

## 허용 가능한 다음 단계

Execution Candidate Planner는 다음 조건에서만 새 PR로 허용한다.

- 최신 main에서 새 브랜치 생성
- source-only planner
- 모든 실행 관련 플래그는 기본값 false
- ODA output contract를 소비만 함
- ODA internals 직접 호출 금지
- `src/main.py` 직접 등록 금지
- `config/worker_manifest.json` 직접 수정 금지

## 금지

- CAD 명령 실행
- 파일 저장/내보내기 실행
- XiCAD alias execution
- original DWG mutation
- production live runner
- operator approval 자동화

## PR #105 처리

현재 PR #105는 stale / mergeable false / `src/main.py` 포함이므로 그대로 merge하지 않는다. 필요한 경우 Agent 2에게 최신 main 기반 source-only 재작성 지시를 내린다.
