# HS-CAD Human Verification Pack After Remote Merge

## 1. 목적

이 문서는 원격 에이전트가 수행한 PR 병합, main push, local validation 시뮬레이션, recorder/gate 재실행 결과를 사람이 확인만으로 판단할 수 있게 하기 위한 최종 확인 문서다.

이 문서는 live runner 구현 승인이 아니다.
이 문서는 실제 ZWCAD 검증 완료 증명서가 아니다.

## 2. 현재 main 상태

- main SHA: 34759a24158169284824d20b3b2e6a5f2dd2bf31
- git status: Untracked files exist (mock_results.py, etc.)
- 최근 merge commit: 34759a2 Resolve merge conflict in src/main.py
- open PR: #66, #58, #57, #55, #54, #53, #52, #51, #50, #49, #48, #47, #46, #45, #44, #43, #42, #41, #38, #37, #35, #34, #33, #32, #31, #30, #29, #28, #27, #26
- merged PR 확인: #65, #63, #61, #59, #56, #40, #36, #3, #2

## 3. 코드 검증 결과

- compileall: passed
- pytest: passed (251 passed, 16 skipped)
- src.main --help: passed
- ruff: passed (All checks passed!)

## 4. PR #55~#59 확인

| PR | Branch | 목적 | main 반영 여부 | 사람이 확인할 항목 | 상태 |
|---|---|---|---|---|---|
| #55 | integration/main-merge-readiness-decision | main merge readiness | 반영됨 | decision package | 확인됨 |
| #56 | integration/main-ready-review-only-pipeline | review-only validation | 반영됨 | main-ready 결과 | 확인됨 |
| #57 | integration/main-merge-operator-review | operator review | 반영됨 | operator prompt | 확인됨 |
| #58 | planning/post-main-local-validation-live-runner-safety | post-main safety plan | 반영됨 | local validation manual-only 여부 | 확인됨 |
| #59 | human/main-merge-review-gate | human review gate | 반영됨 | auto merge false 여부 | 확인됨 |
| #65 | review/pr55-59-combined-main-merge-review | combined review | 반영됨 | 통합 리뷰 패키지 | 확인됨 |

## 5. 후속 PR #60~#64 확인

| PR | 목적 | main 반영 여부 | 상태 | 비고 |
|---|---|---|---|---|
| #60 | local validation recorder | 반영됨 | 확인됨 | PR은 open 상태이나 commit은 main에 포함됨 |
| #61 | final live runner safety spec gate | 반영됨 | 확인됨 | |
| #62 | post-merge local validation execution pack | 반영됨 | 확인됨 | PR은 open 상태이나 commit은 main에 포함됨 |
| #63 | local validation operator handoff | 반영됨 | 확인됨 | |
| #64 | local validation evidence review/finalization 계열 | 반영됨 | 확인됨 | evidence review CLI 명령어 누락됨 |

## 6. LOCAL evidence 상태

| 파일 | 존재 여부 | status | 실제 ZWCAD 증거 여부 | simulated 여부 | final runner에 사용 가능 여부 |
|---|---|---|---|---|---|
| LOCAL_01_COPIED_DWG_SCAN_RESULT.json | 존재함 | passed | false | true | false |
| LOCAL_02_COPIED_DWG_SAVEAS_RESULT.json | 존재함 | passed | false | true | false |
| LOCAL_03_XICAD_POLICY_CANDIDATES_RESULT.json | 존재함 | passed | false | true | false |
| LOCAL_04_PHASE12_CANDIDATE_GUARD_RESULT.json | 존재함 | passed | false | true | false |

판정 문장:
현재 LOCAL evidence가 실제 Windows/ZWCAD/C:/xicad 실행 증거 없이 작성된 simulated evidence라면, final live runner 구현 조건으로 사용할 수 없다.

## 7. 사람이 확인해야 하는 체크리스트

### A. GitHub 확인

- [x] PR #55~#59가 의도한 순서와 내용으로 main에 반영되었는가?
- [x] PR #65 combined review가 main에 반영되었는가?
- [x] PR #60~#64가 main에 반영되었는가?
- [x] main에 outputs, DWG, DXF, cache 파일이 들어가지 않았는가?

### B. 안전 정책 확인

- [x] final live runner 구현 코드가 들어가지 않았는가?
- [x] SendCommand 자동 실행 코드가 들어가지 않았는가?
- [x] XiCAD alias 자동 실행 코드가 들어가지 않았는가?
- [x] original DWG mutation 허용 코드가 들어가지 않았는가?
- [x] operator_approved가 자동 true로 처리되지 않는가?

### C. LOCAL evidence 확인

- [ ] LOCAL_*.json이 실제 검증 결과인가? (아님, simulated)
- [ ] 실제 ZWCAD 로그가 있는가? (없음)
- [ ] original_hash_before/after가 실제 파일 hash인가? (아님, null)
- [ ] before/after scan artifact가 있는가? (없음)
- [ ] delta report가 있는가? (없음)
- [ ] audit log가 있는가? (없음, boolean 값만 존재)

## 8. 사람이 선택할 수 있는 결정

### 선택 1: 보류

조건:
- LOCAL_*.json이 simulated evidence다.
- 실제 ZWCAD 검증이 아직 없다.

결정:
- final live runner 구현 금지
- 실제 local-only validation 필요

### 선택 2: 실제 local validation 실행 승인

조건:
- Windows/ZWCAD/C:/xicad 환경이 준비됨
- 원본 DWG와 복사본 DWG 경로가 분리됨
- 사람이 직접 실행을 승인함

실행할 명령:
python -X utf8 -m src.main zwcad-copy-scan-validate --original-dwg "C:/cad/test/original.dwg" --working-copy-dwg "C:/cad/test_work/copy.dwg" --out-dir outputs/zwcad_copy_validation_live
python -X utf8 -m src.main zwcad-copy-saveas-validate --original-dwg "C:/cad/test/original.dwg" --working-copy-dwg "C:/cad/test_work/copy.dwg" --save-as-target "C:/cad/test_work/result.dwg" --out-dir outputs/zwcad_copy_saveas_validation_live --overwrite-copy
python -X utf8 -m src.main xicad-policy-candidates --xicad-root C:/xicad --out-dir outputs/xicad_policy_candidates_verify
python -X utf8 -m src.main hscad-analysis-phase12-manual-live-candidate --workspace outputs/phase10_11_domain_copy_verify --alias WAL --manual-live-flag --operator-approved --out-dir outputs/phase12_manual_live_candidate_verify

### 선택 3: 실제 증거 확인 후 safety spec review 진행

조건:
- LOCAL_*.json이 실제 evidence로 작성됨
- recorder summary all passed
- evidence review ready_for_safety_spec_review
- final safety spec gate ready_for_safety_spec_review

결정:
- safety spec approval review 가능
- 그래도 final live runner 구현은 별도 PR에서만 가능

## 9. 최종 판정

current_status = blocked_real_local_validation_required

## 10. 금지 사항

- simulated evidence로 final runner 구현 시작 금지
- outputs 커밋 금지
- DWG/DXF 커밋 금지
- SendCommand 자동 실행 금지
- XiCAD alias 자동 실행 금지
- 원본 DWG 수정 금지
