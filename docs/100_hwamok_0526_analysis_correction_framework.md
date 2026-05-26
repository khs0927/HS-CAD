# Hwamok 0526 Analysis & Correction Framework

## 1. Core Principles (우선 분석 원칙)
- **ODA/DXF/fileized 우선 분석 원칙**: 도면의 초기 분석은 반드시 ODA File Converter를 거쳐 추출된 `fileized` 데이터(DXF 및 JSON)를 통해서만 진행해야 합니다.
- **COM/SaveAs/SendCommand 금지 및 승인 게이트**: ZWCAD COM을 통한 `SendCommand`나 `SaveAs` 등 도면 상태를 변형하는 라이브 CAD 명령은 기본적으로 엄격히 금지되며, 반드시 승인 게이트를 통과해야 합니다.
- **실행 게이트 (복사본 수정)**: 실제 도면 수정(Mutation)은 원본 보호를 위해 절대 원본 DWG에서 진행하지 않으며, 반드시 **복사본 DWG**에서만 진행하도록 강제하는 실행 게이트를 통과해야 합니다.

## 2. Current Error Candidates (오류 후보 점검 결과)
### 텍스트 핸들별 판단 (8개 오류 후보)
현재 화목동 0526 도면에서 발견된 8개의 문제성 텍스트 핸들에 대해 공간적 포함 관계(Spatial Containment)와 의미 역할(Text Roles) 기반으로 정밀 판단을 진행합니다.

### 후보 처리 기준 (Handling Criteria)
- **0 레이어 과다 (Excessive Layer 0)**: 도면 객체의 상당수가 '0' 레이어에 방치된 경우 분류를 요구합니다.
- **익명 블록 (Anonymous Blocks)**: `*U` 형태의 익명 블록이 공간 경계를 침범하거나 분석을 방해할 경우 분해(Explode) 또는 정규화 대상이 됩니다.
- **텍스트 높이 이상 (Abnormal Text Height)**: 표준 척도 스케일을 벗어나는 텍스트 요소들을 식별하고 수정 대상 후보로 지정합니다.

## 3. Agent Workflow (다른 에이전트가 따라야 할 단계별 명령 순서)
다음은 다른 분석/수정 에이전트가 화목동 0526 도면을 처리할 때 따라야 하는 순차 프레임워크입니다.

1. `corpus-run prepare` (샘플 및 작업 공간 격리)
2. `corpus-run fileize` (안전한 DWG -> DXF 변환)
3. `corpus-run validate & index` (JSON 데이터 변환 및 SQLite DB 인덱싱)
4. `hscad-area-elements` 및 `hscad-spatial-containment` (기하학적 경계 및 공간 관계 그래프 생성)
5. `hscad-text-roles` (텍스트 의미 및 속성 분류)
6. `hscad-analysis-phase12-manual-live-candidate` (복사본 도면 기반 수정 후보군 생성)

## 4. Gates & Conditions
### 중단 조건 (Halt Conditions)
- 원본 DWG 경로에 대한 직/간접적 쓰기 시도 감지 시
- 승인되지 않은 `ZWCAD COM` 라이브 실행 시도 시

### 통과 조건 (Pass Conditions)
- 복사본 작업 공간 내에서 에러 없이 아티팩트(`JSON`, `MD`)가 모두 생성되었을 때
- Dry-run 검증이 오류 없이 통과되었을 때

### Dry-run 계획 필수 필드 (Required Fields)
실제 수정을 위한 Dry-run 계획 시 다음 필드가 반드시 포함되어야 합니다:
- `target_file` (대상 복사본 파일)
- `mutation_type` (수정 유형)
- `pre_condition` (수정 전 상태)
- `post_condition` (예상되는 수정 후 상태)
