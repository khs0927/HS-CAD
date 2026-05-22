# HS-CAD Intelligent Agent Workflow

## 목적

HS-CAD Intelligent Agent Workflow는 사용자가 자연어로 작업을 지시했을 때 다음을 자동으로 판단하기 위한 운영 레이어입니다.

1. 어떤 작업인지 이해한다.
2. 어떤 도구를 먼저 써야 하는지 결정한다.
3. 어떤 도구는 보조로 써야 하는지 결정한다.
4. 어떤 단계는 위험해서 사람 검토 후 실행해야 하는지 분리한다.
5. 누락된 입력과 환경 조건을 알려준다.
6. 진행 방향을 JSON/Markdown 리포트로 남긴다.

## 사고 흐름

```text
User Task
  ↓
Intake
  ↓
Intent Classification
  ↓
Capability / Availability Check
  ↓
Tool Priority Decision
  ↓
Safety Gate
  ↓
Workflow Plan
  ↓
Safe Candidate Execution or Review Hold
  ↓
Report
```

## Intent 분류

| Intent | 의미 | 우선 도구 |
|---|---|---|
| floorplan_to_cad | 이미지/PDF 도면을 CAD 초안으로 변환 | floorplan-analyze, neuro_seq_cad |
| dwg_inspection | 기존 DWG 검토 | scan, layers, blocks, texts, analyze-architecture |
| dwg_change_review_first | 기존 DWG 수정 요청 | scan → audit → run-command dry-run |
| xicad_arch_draw | 벽/문/창/단열/계단 등 XiCAD 건축 작성 | XiCAD taxonomy/search/context |
| xicad_layer_manage | 레이어/켜 관리 | XiCAD layer commands, dry-run plan |
| xicad_area_calc | 면적/수량/표 | XiCAD area commands, quantity |
| hybrid_steel_workflow | H빔/철골/구조 | HSSTEEL, ArchiOffice, structure audit |
| general_safe_inspection | 입력 정보가 부족한 일반 요청 | tool registry, environment check |

## Safety Gate

| 등급 | 의미 |
|---|---|
| safe_read_only | 읽기/검토만 수행 |
| safe_file_output | 새 파일만 생성 |
| review_gated | 사람 검토 후 별도 실행 필요 |
| blocked | 자동 진행 금지 |

## 적용 원칙

- 기본은 planning-only입니다.
- 기존 DWG를 자동 수정하지 않습니다.
- 원본 DWG에 Save하지 않습니다.
- SaveAs, Delete, Purge, Explode, Block Definition Edit는 자동 실행하지 않습니다.
- XiCAD 명령은 taxonomy/RAG로 추천하고, recipe 검증 전에는 실행하지 않습니다.
- neuro_seq_cad의 DXFBuilder는 기본 출력으로 유지합니다.
