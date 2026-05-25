# HS-CAD Main Merge Readiness Decision — 작업 보고서

- 작업 기간: 2026-05-25 (Asia/Seoul)
- 대상 브랜치: `integration/main-merge-readiness-decision`
- 대상 PR: [#55 Add main merge readiness decision package](https://github.com/khs0927/HS-CAD/pull/55)
- 베이스 브랜치: `integration/post-pr53-main-merge-local-validation`
- PR 상태: **OPEN** (non-draft)
- Decision status: `ready_for_human_main_merge_review`

---

## 1. 작업 개요

PR #53, #54의 컨텍스트를 모두 반영한 **main 병합 readiness 결정 패키지**를 도입했습니다. 이 PR은 **main에 자동 병합하지 않고**, 인간 검토자(human reviewer)가 review-only/plan-only 파이프라인에 한해 병합 여부를 판단할 수 있도록 다음을 제공합니다.

1. Gate 기반 readiness 결정 로직(`src/analysis/main_merge_readiness_decision.py`)
2. 워커 진입점(`src/workers/main_merge_readiness_decision_worker.py`)
3. Typer 기반 CLI 명령(`hscad-main-merge-readiness-decision`)
4. 결정 패키지 아티팩트 4종 생성:
   - `MAIN_MERGE_READINESS_DECISION.json`
   - `MAIN_MERGE_READINESS_DECISION.md`
   - `MAIN_MERGE_PR_BODY_DRAFT.md`
   - `POST_MERGE_LOCAL_VALIDATION_PROMPT.md`

추가로 코드 품질 점검(ruff/pyflakes) 과정에서 발견된 **3개의 잠재적 결함**을 수정했습니다.

---

## 2. 신규 / 수정 파일

### 2.1 PR #55 commit `613aa4b` — main merge readiness decision package 도입

| 분류 | 경로 |
| --- | --- |
| 분석 코어 | `src/analysis/main_merge_readiness_decision.py` |
| 워커 | `src/workers/main_merge_readiness_decision_worker.py` |
| CLI | `src/app/main_merge_readiness_cli.py` |
| 테스트 | `tests/test_main_merge_readiness_decision.py` |
| 프롬프트 | `docs/99_main_merge_readiness_decision_prompt.md` |
| 보고서 | `docs/100_main_merge_readiness_decision_report.md` |
| 워커 매니페스트 패치 | `config/worker_manifest.main_merge_decision.patch.json` |
| 적용 가이드 | `README_APPLY_MAIN_MERGE_DECISION.md` |
| 임포트 등록 패치 | `MAIN_IMPORT_MAIN_MERGE_DECISION_PATCH.txt` |
| 수정 | `src/main.py` 에 `import src.app.main_merge_readiness_cli` 한 줄 추가 |

### 2.2 PR #55 follow-up commit `6954104` — 코드 품질 / 어댑터 정합성 개선

본 작업에서 발견·수정한 사항입니다.

| 파일 | 변경 내용 |
| --- | --- |
| `src/adapters/zwcad_com_adapter.py` | `__init__`에 `version=None`, `start_if_needed=True` 키워드 인자 추가, `active_progid` 속성 노출. 버전 핀(2024/2025/2026) 시 ProgID 후보 우선순위 분기. 기존 `ZWCADCOMAdapter(visible=...)` 호출은 완전 후방호환. |
| `src/neuro_seq_cad/config/layer_schema.py` | `if TYPE_CHECKING: import ezdxf` 추가하여 `setup_layers / _ensure_linetype`의 forward-ref 타입힌트 해소. ruff F821 4건 중 2건 해결. |
| `src/neuro_seq_cad/io/coordinate_system.py` | `if TYPE_CHECKING: import numpy` 추가하여 `transform_points_numpy`의 타입힌트 해소. ruff F821 4건 중 2건 해결. |
| `src/analysis/main_merge_readiness_decision.py` | 미사용 헬퍼 `_safe_flag_false` 제거(dead code). |

---

## 3. 검증 결과

### 3.1 정적 검증

| 검사 | 명령 | 결과 |
| --- | --- | --- |
| Compile / import 무결성 | `python -X utf8 -m compileall -q src tests` | 통과 (출력 없음 = 깨끗) |
| ruff (신규 4파일) | `ruff check src/analysis/... src/workers/... src/app/... tests/test_main_merge_readiness_decision.py` | `All checks passed!` |
| ruff F821 (전체) | `ruff check src tests --select F821` | `All checks passed!` (수정 전 4건 → 수정 후 0건) |
| ruff 핵심군 (전체) | `ruff check src tests --select E9,F63,F7,F82` | 오류 0건 |

### 3.2 테스트 결과

| 단계 | 명령 | 결과 |
| --- | --- | --- |
| 타겟 테스트 | `python -X utf8 -m pytest -q tests/test_main_merge_readiness_decision.py` | **3 passed** |
| 전체 테스트 | `python -X utf8 -m pytest -q` | **200 passed, 16 skipped** |
| 어댑터 확장 후 회귀 | `python -X utf8 -m pytest -q` | **200 passed, 16 skipped** (동일) |

16개의 skipped 테스트는 모두 `tests/integration/**`의 ZWCAD/XiCAD live 통합 테스트로, `pytest --run-integration` 또는 `ZWCAD_INTEGRATION_TEST=1`에서만 활성화됩니다. 추가로 각 테스트는 `ZWCAD_TEST_DWG`, `XICAD_ROOT` 등의 환경 변수가 있어야 실제로 수행됩니다(PR #55의 안전 정책에 따라 본 단계에서는 자동 실행하지 않음).

### 3.3 CLI smoke

| 명령 | 결과 |
| --- | --- |
| `python -X utf8 -m src.main --help` | 통과. 모든 `hscad-*` 명령(`hscad-main-merge-readiness-decision` 포함) 정상 등록 확인. |
| `python -X utf8 -m src.main hscad-main-merge-readiness-decision` | 통과. 4개 artifact 생성. status = `ready_for_human_main_merge_review`. |

생성된 아티팩트:

```
outputs/main_merge_readiness_decision/
├── MAIN_MERGE_READINESS_DECISION.json     7320 B
├── MAIN_MERGE_READINESS_DECISION.md       2386 B
├── MAIN_MERGE_PR_BODY_DRAFT.md            1210 B
└── POST_MERGE_LOCAL_VALIDATION_PROMPT.md  2432 B
```

---

## 4. 발견·수정한 잠재 결함 상세

### 4.1 `ZWCADCOMAdapter` 시그니처 불일치 (TypeError)

- 위치: `src/adapters/zwcad_com_adapter.py` vs `tests/integration/test_zwcad{2025,2026}_*.py`
- 증상: integration 테스트들은 `ZWCADCOMAdapter(version="2026", start_if_needed=True)` 형태로 호출하지만 어댑터의 `__init__`은 `visible=True`만 받음. integration이 default-skip이라 평소 단위테스트에서는 노출되지 않았으나, 사용자가 ZWCAD를 켜고 `ZWCAD_INTEGRATION_TEST=1`로 실행하면 즉시 `TypeError: ZWCADCOMAdapter.__init__() got an unexpected keyword argument 'version'`이 발생.
- 조치: 어댑터를 확장하여 다음 의미론을 갖도록 구현했습니다.
  - `version`: `"2026"`, `"2025"`, `"2024"`, 또는 `None`. 지정 시 해당 버전의 ProgID 우선순위 적용.
  - `start_if_needed`: `False`이면 `GetActiveObject`만 시도하고 새 ZWCAD를 spawn하지 않음(read-only friendly).
  - `active_progid`: 실제 연결된 ProgID 노출(테스트 assertion 대상).
  - 기존 `ZWCADCOMAdapter(visible=True)` 호출은 100% 후방호환.
- 안전성: `connect()` 자체는 SendCommand를 호출하지 않으며, 본 PR의 정책 `sendcommand_allowed_by_default=false` / `cad_execution_allowed_by_default=false`를 그대로 유지합니다.

### 4.2 ruff F821 — 미정의 이름 forward-ref

- 위치
  - `src/neuro_seq_cad/config/layer_schema.py` (setup_layers, _ensure_linetype의 `doc: "ezdxf.document.Drawing"`)
  - `src/neuro_seq_cad/io/coordinate_system.py` (`points: "numpy.ndarray"`, 리턴 타입)
- 증상: 모듈 최상위에서 `ezdxf`, `numpy`를 import 하지 않은 상태로 forward-ref 문자열 annotation을 사용. `from __future__ import annotations` 덕분에 런타임 오류는 발생하지 않지만, ruff F821 4건 보고. 타입체커·IDE에서 정의로 점프 불가능한 상태.
- 조치: `if TYPE_CHECKING: import ezdxf` / `import numpy` 가드를 추가하고, 문자열 따옴표를 제거해 `from __future__ import annotations`가 자연스럽게 lazy 처리하도록 정렬. ruff 0건.

### 4.3 Dead helper `_safe_flag_false`

- 위치: `src/analysis/main_merge_readiness_decision.py`
- 증상: 정의만 되어 있고 호출처가 없음.
- 조치: 함수 제거. 동등한 인라인 비교(`safety.get(key) is True`)는 이미 본문에 있음.

---

## 5. 안전 확인 (PR #55 Decision Package 일치)

| 키 | 값 |
| --- | --- |
| `main_direct_push_allowed` | `false` |
| `main_merge_requires_human_review` | `true` |
| `final_live_runner_implemented` | `false` |
| `final_live_runner_allowed` | `false` |
| `cad_execution_allowed_by_default` | `false` |
| `zwcad_com_allowed_by_default` | `false` |
| `sendcommand_allowed_by_default` | `false` |
| `xicad_alias_execution_allowed_by_default` | `false` |
| `domain_rule_command_execution_allowed` | `false` |
| `copied_dwg_live_validation_allowed_in_main_readiness` | `false` |
| `local_only_validation_required_before_live_runner` | `true` |

본 작업은 위 안전 정책을 **단 한 건도 위반하지 않았습니다**. 어댑터 시그니처 수정 역시 read-only `GetActiveObject`/`CreateObject` 결과만 노출하며, SendCommand는 별도 `run_command()` 경로로 격리된 채 본 PR 단계에서는 호출되지 않습니다.

ZWCAD가 사용자 측에서 켜져 있다는 컨텍스트가 있었지만, 자동 SendCommand·자동 alias 실행·원본 DWG mutation은 본 PR의 핵심 가치 명제이므로 시도하지 않았습니다. ZWCAD 환경에서의 실제 live validation은 main 병합 후 별도 수동 단계(`docs/98_local_only_zwcad_xicad_validation_runbook.md`)로 남아 있습니다.

---

## 6. Allowed / Disallowed Scope

### Allowed in this PR

- review-only analysis pipeline
- plan-only Domain Rule bridge
- copied-DWG validation planning
- manual live candidate guard
- safety policy docs

### Disallowed in this PR

- final live runner
- ZWCAD COM SendCommand execution
- XiCAD alias execution
- Domain Rule Command Plan execution
- original DWG mutation
- automatic operator approval

---

## 7. 변경 이력 (PR #55 브랜치 상)

| 커밋 | 요약 |
| --- | --- |
| `613aa4b` | feat: add main merge readiness decision package |
| `6954104` | fix: ruff F821 cleanup + extend ZWCADCOMAdapter API |

브랜치는 `origin/integration/main-merge-readiness-decision`로 푸시 완료. PR #55 OPEN(non-draft).

---

## 8. 커밋하지 않은 워크스페이스 산출물(의도적 제외)

다음 디렉터리/파일은 의도적으로 커밋에서 제외했습니다(.gitignore 또는 작업 산출물 정책에 따름):

- `_main_merge_decision_patch/`, `_main_readiness_patch/`, `_post_pr53_patch/`, `_phase*_patch/`, `_final_todo_patch/`
- `outputs/**` (예: `outputs/main_merge_readiness_decision/*`)

---

## 9. 남은 TODO

1. **인간 검토자가 PR #55 decision package를 검토**한 뒤, 별도 절차로 main 병합 여부를 판단해야 합니다.
2. **Windows/ZWCAD/XiCAD local-only validation**은 main 병합 이후에도 **수동 단계**로 남아 있습니다. `docs/98_local_only_zwcad_xicad_validation_runbook.md`에 정의된 절차에 따라 진행해야 합니다.
3. **Final live runner** 구현은 별도 안전 정책 PR로 분리되어야 하며 본 PR의 범위에서 제외됩니다.

---

## 10. 빠른 검증 명령

```powershell
# 정적 검증
python -X utf8 -m compileall -q src tests
python -X utf8 -m ruff check src tests --select E9,F63,F7,F82,F821

# 단위 + 통합 회귀 (integration 자동 제외)
python -X utf8 -m pytest -q

# CLI smoke
python -X utf8 -m src.main --help
python -X utf8 -m src.main hscad-main-merge-readiness-decision
```

기대값: 200 passed / 16 skipped, ruff All checks passed, decision status `ready_for_human_main_merge_review`.
