# 56. HS-CAD Command-Trace Reverse Analysis Framework

## 1. 목적

이 문서는 도면을 단순한 CAD 객체 목록이 아니라 **어떤 도구와 명령 흐름으로 작성되었는지 추정 가능한 증거 그래프**로 해석하기 위한 HS-CAD 확장 계획이다.

중요한 경계는 명확하다.

- XiCAD의 LISP/FAS/DES 내부 구현을 복호화하거나 해체하지 않는다.
- ZWCAD 원본 DWG를 직접 수정하지 않는다.
- 자동 실행은 `xicad_alias_allowlist`, review gate, copy execution package, operator approval을 통과한 복사본에서만 허용한다.
- 1차 목표는 실제 명령 실행이 아니라 **전/후 scan snapshot delta를 안정적으로 수집하고 signature 후보를 생성하는 것**이다.

즉, 이 프레임워크는 "역공학"이라는 이름을 쓰더라도 내부 코드 해석이 아니라 **블랙박스 관찰 기반 command-trace reconstruction**이다.

## 2. 현재 HS-CAD 기반 자산

이미 프로젝트에 존재하는 구성 요소를 최대한 재사용한다.

| 역할 | 기존 모듈 |
| --- | --- |
| 활성/복사 도면 스캔 | `src.execution.scan_snapshot` |
| 전/후 객체 수량 delta | `src.execution.drawing_delta` |
| 원본 보호 working copy 생성 | `src.execution.dwg_copy_manager` |
| copy scan/save-as 검증 | `src.execution.zwcad_copy_validation` |
| 승인 전 실행 패키지 | `src.execution.safe_execution_package_builder` |
| 안전 실행 경계 | `src.execution.zwcad_xicad_safe_executor` |
| XiCAD alias allowlist | `src.execution.xicad_alias_policy`, `src.execution.xicad_alias_classifier` |
| allowlist plan worker | `src.workers.xicad_alias_allowlist_worker` |
| candidate policy report | `src.execution.xicad_policy_candidate`, `src.workers.xicad_policy_candidate_worker` |
| 도형/공간 분석 기반 | `src.spatial.*`, `src.analysis.*`, `src.graph.*` |

따라서 Step 1은 새 거대 시스템을 만들기보다 `scan_snapshot`과 `drawing_delta`를 확장해 **entity-level delta**를 만드는 것이 맞다.

## 2.1. Local `C:\xicad` 검토 결과

현재 로컬 `C:\xicad` 폴더는 실행 없이 읽기 전용으로 인벤토리화했다.

| 항목 | 값 |
| --- | ---: |
| 전체 파일 수 | 2,373 |
| 전체 크기 | 173,488,032 bytes |
| DWG 라이브러리 블록 | 1,467 |
| XiCAD shortkey alias | 356 |
| ZWCAD PGP alias | 596 |
| wall style group | 9 |
| block/layer rule category | 14 |
| config variable group | 88 |
| steel spec type | 6 |
| policy candidate | 591 |
| blocked candidate | 13 |
| review-required candidate | 578 |

생성된 로컬 산출물:

- `outputs/xicad_reverse_inventory/XICAD_FILE_MANIFEST.json`
- `outputs/xicad_reverse_inventory/XICAD_RULES_EXTRACT.json`
- `outputs/xicad_reverse_inventory/XICAD_POLICY_CANDIDATES_FROM_LOCAL.json`
- `outputs/xicad_reverse_inventory/XICAD_REVERSE_INVENTORY_SUMMARY.json`
- `outputs/xicad_signature_seeds_local/XICAD_SIGNATURE_SEEDS.json`
- `outputs/xicad_signature_seeds_local/XICAD_SIGNATURE_SEEDS.md`

이 검토는 `.fas`, `.des`, `.zelx`, `.zrx`, `.arx`, `.dll` 같은 바이너리를 해체하지 않는다. 파일명, 확장자, 크기, 그리고 텍스트 설정/단축키/규격표만 안전하게 읽는다.

텍스트 규칙 기반 signature seed:

- `WAL`: wall style 9개에서 평행선 pair, 레이어 후보, 두께 후보 추출
- `D1`: door config에서 opening gap + block/arc insert, 폭 후보 추출
- `W1`: window config에서 opening gap + block/arc insert 후보 추출

모든 seed는 `requires_human_review=true`이며, 아직 `config/xicad_command_signatures.json`로 승격하지 않는다.

## 3. 아키텍처

### Layer 1. Safe Observation & Delta Layer

목표: 명령 실행 전후의 도면 상태를 안전하게 관찰한다.

입력:

- `DOMAIN_RULE_COMMAND_PLAN.json`
- `DOMAIN_RULE_REVIEW_GATE.json`
- `DOMAIN_RULE_SIGNOFF_MANIFEST.json`
- original DWG
- working copy DWG
- save-as target

처리:

1. `prepare_working_copy()`로 원본과 다른 working copy를 만든다.
2. `build_scan_snapshot()`으로 before snapshot을 만든다.
3. dry-run 단계에서는 실제 XiCAD 명령을 실행하지 않고 계획만 기록한다.
4. 향후 approved-copy 단계에서만 allowlist 통과 alias를 adapter boundary 뒤에서 실행한다.
5. after snapshot을 다시 만들고 `build_delta_report()`를 생성한다.

확장 필요:

- 현재 `drawing_delta`는 count delta 중심이다.
- 다음 단계에서 handle, layer, entity type, geometry hash를 기준으로 `added`, `removed`, `changed`, `unchanged`를 분리하는 `entity_delta`가 필요하다.

### Layer 2. Command Signature Model Layer

목표: entity-level delta를 명령어 signature 후보로 추상화한다.

예시 signature:

```json
{
  "alias": "WAL",
  "status": "candidate",
  "source": "black_box_delta",
  "safety": {
    "execution_scope": "approved_copy_only",
    "original_dwg_mutation": false
  },
  "observed_delta": {
    "added_type_counts": {"LINE": 2},
    "added_layer_patterns": ["*WAL*", "*WALL*"],
    "geometry_patterns": [
      {"kind": "parallel_line_pair", "min_count": 1}
    ]
  },
  "confidence": 0.0,
  "requires_human_review": true
}
```

저장 위치 후보:

- `config/xicad_command_signatures.json`
- 또는 검증 전까지 `outputs/xicad_command_signatures/*.json`

원칙:

- `config/` 승격은 사람이 리뷰한 뒤 별도 PR에서 한다.
- generated signature는 항상 `requires_human_review=true`로 시작한다.

### Layer 3. Evidence Graph Matching Layer

목표: 대상 도면 scan 결과에서 signature와 유사한 객체 패턴을 찾는다.

기존 HS-CAD 분석 축과 연결:

- `src.cad_core.entity_model`로 스캔 객체를 정규화한다.
- `src.spatial.geometry`, `src.spatial.graph_exporter`, `src.graph.networkx_graph_audit` 계층을 활용한다.
- line pair, block insert, text leader, opening trim 같은 관계를 graph edge로 만든다.

초기 매칭 범위:

- `WAL`: 같은 레이어 계열의 평행 LINE/LWPOLYLINE pair
- `D1/W1`: wall pair 사이의 opening gap + door/window block 또는 arc/line 조합
- `COL`: 반복 사각/블록 삽입 + structural layer

### Layer 4. Command Trace Reconstruction Layer

목표: 발견된 signature instance 사이의 순서를 추정한다.

초기 규칙:

- opening이 wall line을 끊고 있으면 wall 계열 instance가 먼저, door/window 계열 instance가 나중이다.
- dimension/text annotation이 geometry를 참조하면 geometry가 먼저다.
- 같은 block family가 grid/column line 위에 정렬되면 grid 또는 structural base가 먼저다.

출력 후보:

```json
{
  "drawing_id": "sample",
  "status": "review_required",
  "instances": [],
  "ordering_edges": [],
  "warnings": [
    "Chronology is inferred from geometry, not from CAD command logs."
  ]
}
```

### Layer 5. Validation & Insight Layer

목표: 매칭되지 않은 객체와 수작업 흔적을 검출한다.

리포트 항목:

- signature와 매칭된 객체 비율
- orphan entity 목록
- suspicious manual drafting pattern
- layer naming mismatch
- command signature confidence
- 사람이 확인해야 할 review queue

주의:

- "수작업으로 대충 그렸다" 같은 단정 표현은 리포트에 쓰지 않는다.
- 대신 "matching signature not found", "manual drafting candidate", "requires reviewer confirmation"처럼 증거 중심으로 표현한다.

## 4. Step 1: Sandbox Delta Extractor Pilot

첫 구현 단위는 실제 XiCAD 자동 실행이 아니라 fake/fixture 기반 delta 추출기다.

### Step 1A. Fake Entity Delta

추가할 후보 모듈:

- `src.execution.entity_delta`

기능:

- `build_entity_delta(before_objects, after_objects)`
- handle이 있으면 handle 기준 비교
- handle이 없으면 `(entity_type, layer, geometry fingerprint)` 기준 비교
- 결과를 `added`, `removed`, `changed`, `unchanged`, `summary`로 반환

테스트:

- `tests/test_entity_delta.py`
- fake before/after 객체로 WAL 유사 parallel line 2개 추가를 검증

현재 상태:

- 구현 완료
- `added`, `removed`, `changed`, `unchanged` 분리 완료
- handle이 없을 때 geometry fingerprint 기반 비교 지원

### Step 1B. Delta Signature Candidate

추가할 후보 모듈:

- `src.execution.xicad_signature_candidate`
- `src.workers.xicad_signature_candidate_worker`
- CLI: `python -X utf8 -m src.main xicad-signature-candidate`

기능:

- `build_signature_candidate(alias, delta_report)`
- added 객체의 layer/type/geometry pattern을 요약
- 항상 `status="candidate"`와 `requires_human_review=true`

테스트:

- `tests/test_xicad_signature_candidate.py`
- WAL fixture delta에서 `parallel_line_pair` 후보가 만들어지는지 검증

현재 상태:

- 구현 완료
- WAL-like fixture에서 `parallel_line_pair` 후보 생성 확인
- 모든 후보는 `requires_human_review=true`, `auto_promote_to_config=false`
- before/after snapshot JSON을 입력받아 `ENTITY_DELTA.json`, `XICAD_SIGNATURE_CANDIDATE.json`, `XICAD_SIGNATURE_CANDIDATE.md`를 생성하는 worker/CLI 구현 완료
- demo output: `outputs/xicad_signature_candidate_demo/result/`

### Step 1C. Local XiCAD Signature Seed

추가된 모듈:

- `src.execution.xicad_signature_seed`
- `src.workers.xicad_signature_seed_worker`
- CLI: `python -X utf8 -m src.main xicad-signature-seeds`

기능:

- `C:\xicad`의 텍스트 설정과 규칙 파일을 읽어 signature seed를 만든다.
- 현재 로컬 환경에서는 `WAL`, `D1`, `W1` seed가 생성된다.
- protected binary internals는 읽지 않는다.
- ZWCAD를 열지 않고 `SendCommand`도 호출하지 않는다.

테스트:

- `tests/test_xicad_signature_seed.py`
- `tests/test_xicad_signature_seed_worker.py`

### Step 1D. Real ZWCAD Read-Only Probe

ZWCAD가 열려 있을 때 실행 가능한 안전 검증:

- 활성 도면 연결
- `scan_modelspace()` 실행
- `outputs/reverse_probe/ACTIVE_SCAN_SNAPSHOT.json` 저장
- 명령 실행, SendCommand, SaveAs는 하지 않음

이 probe는 real CAD 환경 확인용이며, signature 생성의 필수 조건은 아니다.

## 5. Step 2 이후 로드맵

### Step 2. Approved Copy Delta

- `safe_execution_package_builder`의 `approved_copy_execution` 패키지를 사용한다.
- operator approval이 없는 상태에서는 실행하지 않는다.
- working copy와 save-as target이 original과 다른지 강제한다.
- 실행 후 `before_snapshot`, `after_snapshot`, `entity_delta`, `signature_candidate`를 묶어 저장한다.

### Step 3. Signature Review & Promotion

- `outputs/xicad_command_signatures/*.json` 후보를 사람이 리뷰한다.
- 통과한 것만 `config/xicad_command_signatures.json`로 승격한다.
- 승격 PR에서는 fixture 기반 regression test를 반드시 추가한다.

### Step 4. Target Drawing Matching

- 실제 도면 scan 결과에 signature matcher를 적용한다.
- confidence 낮은 결과는 자동 확정하지 않고 review queue로 보낸다.

### Step 5. Command Trace Report

- command instance graph와 ordering edge를 만든다.
- Markdown/HTML 리포트로 "추정된 작성 흐름"과 "검토 필요 객체"를 제공한다.

## 6. 검증 기준

이 프레임워크의 완료 조건은 다음 순서로 잡는다.

1. Unit: fake object delta에서 added/removed/changed가 안정적으로 분리된다.
2. Unit: WAL-like fixture에서 signature candidate가 생성된다.
3. Unit: unknown/destructive alias는 기존 allowlist 정책대로 실행 불가다.
4. Integration dry-run: active ZWCAD scan snapshot을 저장하되 도면을 변경하지 않는다.
5. Approved copy: operator-approved package에서만 working copy execution을 허용한다.
6. Review: signature 후보는 config 승격 전 사람이 확인한다.

## 7. 지금 당장 실행 가능한 안전 명령

```powershell
python -X utf8 -m pytest -q `
  tests/test_entity_delta.py `
  tests/test_xicad_signature_candidate.py `
  tests/test_xicad_signature_candidate_worker.py `
  tests/test_xicad_signature_seed.py `
  tests/test_xicad_signature_seed_worker.py `
  tests/test_xicad_alias_allowlist.py `
  tests/test_xicad_policy_candidate_generator.py `
  tests/test_xicad_safe_runner.py `
  tests/test_safe_execution_harness.py `
  tests/test_zwcad_copy_execution_validation.py
```

ZWCAD가 열려 있을 때도 위 테스트는 실제 도면을 수정하지 않는다.

## 8. 결론

프로젝트에 맞는 첫 번째 개발 액션은 "WAL을 실제로 자동 실행해보기"가 아니다. 먼저 `scan_snapshot`과 `drawing_delta`를 확장해 **entity-level delta와 signature candidate를 fixture로 검증**해야 한다. 그 다음에야 review gate와 approved working copy를 통과한 명령만 real ZWCAD 관찰 루프에 연결할 수 있다.
