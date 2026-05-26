# 05. Agent 3 – Fast Scanner / Quality Gate / GitHub Watcher Direction

## 역할

Agent 3은 opencode desktop의 gpt-oss-120b다. 복잡한 아키텍처 판단을 하지 않는다. 감시, 테스트, 보고만 한다.

## 바로 다음 작업

PR #111을 검증한다.

## 검증 범위

- PR #111 head를 최신 main 위에 임시 병합하여 확인한다.
- 변경 파일이 docs/test 범위에 머무는지 확인한다.
- `src/main.py`, `config/worker_manifest.json`, `.github/workflows/`, CAD adapter, ODA converter가 수정되지 않았는지 확인한다.
- targeted test, compileall, `src.main --help`, full pytest를 실행한다.
- outputs/artifacts/binary 파일이 커밋 대상에 없는지 확인한다.

## 보고서

로컬 보고서 파일:

```text
outputs/agent3_pr111_quality_gate_report.md
```

포함:

1. main commit
2. PR #111 head commit
3. 변경 파일 목록
4. 금지 파일 포함 여부
5. targeted test 결과
6. compileall 결과
7. full pytest 결과
8. artifact scan 결과
9. PASS / REVIEW_REQUIRED / BLOCKED
10. 다음 담당자: Agent 1

## 금지

- merge
- close
- commit
- push
- 코드 수정
- 테스트 skip
- CAD 실행

## 판정

- 모든 테스트가 통과하고 금지 파일 변경이 없으면 PASS.
- docs/test 외 파일이 섞이면 REVIEW_REQUIRED 또는 BLOCKED.
- high-risk 파일, live CAD 실행, artifact 커밋 가능성이 보이면 BLOCKED.
