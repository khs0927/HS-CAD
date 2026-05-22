# XiCAD Deep Orchestrator Stage-2 Prep

## 목적

1차 구현으로 추가된 XiCAD taxonomy/search/context/recipe 구조를 2단계로 연결하기 전에 안전 정책을 보정한다.

핵심 원칙은 default deny다. XiCAD 명령은 실무적으로 유용하지만, FAS/ZELX/DES 내부 인자 구조가 보호되어 있으므로 실제 ZWCAD + XiCAD 세션에서 검증되기 전까지 자동 실행 후보가 될 수 없다.

## 유지하는 구조

- XiCAD 단축키 파일 기반 taxonomy
- query/category 기반 검색형 context
- CP949, UTF-8, EUC-KR, latin1 fallback
- 위험 명령 BLOCKED/HIGH_RISK 분류
- 기존 DXFBuilder 기본 출력
- 기존 XiCADAdapter, XiCAD Safe Bridge, RuleEngine 계층

## 안전 정책

위험도 판단은 `src/orchestrator/xicad_safety_policy.py`에서 중앙 관리한다.

| Risk | 의미 |
|---|---|
| SAFE_LOOKUP | 조회/문맥 제공 전용 |
| INTERACTIVE_PREVIEW | 대화형 가능성이 있어 preview/review 필요 |
| REVIEW_REQUIRED | 도면 변경 가능성이 있어 검토 필요 |
| HIGH_RISK | purge, 출력, 백업 등 고위험 |
| BLOCKED | 삭제, 폭파, 닫기 등 자동 실행 금지 |

자동 실행 허용 조건:

```text
recipe_verified == True
recipe_scriptable == True
risk not in {BLOCKED, HIGH_RISK}
```

현재 기본 recipe는 모두 다음 상태다.

```python
verified = False
scriptable = False
```

따라서 `INS`, `AE`, `LC`, `WAL`, `D1`, `W1`, `BE` 모두 review-only다.

## VLM Context

VLM/LLM 프롬프트에는 전체 XiCAD 명령을 주입하지 않는다.

`xicad-safe-context`는 query/category로 후보를 제한하고 각 후보에 다음 정보를 붙인다.

- alias
- function
- category
- risk
- auto_run_allowed
- safety_reasons

## neuro_seq_cad 연결

2단계 연결은 script 생성이 아니라 command plan 생성부터 시작한다.

- DXFBuilder는 계속 canonical output이다.
- `xicad_command_plan.json`은 선택 후처리 출력이다.
- verified recipe가 없으면 `review_only`로 남긴다.
- 검증된 recipe가 생긴 명령만 나중에 `script_candidate`로 승격한다.

## 2단계 진입 기준

- `xicad-safe-context`가 후보 명령을 limit 이하로 제한한다.
- `INS`, `AE`, `LC`가 자동 실행 가능으로 나오지 않는다.
- 위험 명령이 BLOCKED/HIGH_RISK로 분류된다.
- `neuro_seq_cad` command plan이 review-only로 생성된다.
- DXFBuilder가 기본 출력으로 유지된다.
- ZWCAD 없는 환경에서도 테스트가 통과한다.
