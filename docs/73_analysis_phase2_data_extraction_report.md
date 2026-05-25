# Analysis Phase 2 Data Extraction Report

## 구현한 Worker
- `analysis_export_megapack_worker.py`: Analysis export report generation
- `analysis_storage_megapack_worker.py`: Analysis storage manifest generation
- `analysis_report_megapack_worker.py`: Analysis report packaging
- `pipeline_execution_megapack_worker.py`: Pipeline execution reporting
- `final_orchestration_megapack_worker.py`: Final orchestration apply-plan generation

## 입력 Artifact
- 각 Worker는 CLI(`src/app/analysis_shortcut_cli.py`)에서 주입되는 공통 입력 Artifact (`AREA_ELEMENTS.json`, `TEXT_ROLE_INFERENCE.json` 등) 및 각자의 추가 요구 파일을 참조합니다.

## 출력 Artifact
- **Analysis Export**: `ANALYSIS_EXPORT_MANIFEST.json`, `ANALYSIS_EXPORT_SUMMARY.md`, `EVIDENCE_GRAPH_EXPORT.json`
- **Analysis Storage**: `ANALYSIS_STORAGE_MANIFEST.json`, `ANALYSIS_STORAGE_SUMMARY.md`, `EVIDENCE_GRAPH_STORAGE_EXPORT.json`
- **Analysis Report**: `ANALYSIS_REPORT_PACKAGE.json`, `ANALYSIS_REPORT_SUMMARY.md`, `REPORT_PACKAGE_MANIFEST.json`
- **Pipeline Execution**: `PIPELINE_EXECUTION_REPORT.json`, `PIPELINE_EXECUTION_REPORT.md`
- **Final Orchestration**: `FINAL_APPLY_PLAN.json`, `FINAL_APPLY_PLAN.md`, `FINAL_CODEGEN_INVENTORY.json`, `FINAL_TODO_COLLECTOR.json`

## Missing Artifact 처리 방식
- 원칙: **Missing artifact는 hard fail이 아니라 structured warning으로 처리한다.**
- 구현: Worker 실행 중 파일을 찾지 못하면 `warnings` 리스트에 "Missing input artifact: [파일명]"을 추가하고, 실행 결과 Status를 `ok` 대신 `warning`으로 반환하도록 구현했습니다.

## Synthetic Workspace 테스트 결과
- 5개의 Megapack Worker 각각에 대하여 Synthetic workspace 기반의 pytest를 추가했습니다.
- 입력 Artifact가 정상적으로 존재하는 성공 케이스 (`test_*_success`)
- 입력 Artifact가 누락되었을 때 Warning이 기록되는 케이스 (`test_*_missing_input`)
- `tests/test_worker_runtime_contracts.py`를 포함해 총 13개의 pytest가 100% 통과했습니다.

## hscad-analysis-run-all 연결 상태
- `src/app/analysis_shortcut_cli.py` 내의 `DEFAULT_ANALYSIS_WORKERS` 리스트를 Phase 2 워커들로 교체하여 CLI 명령의 루프 흐름에 완벽하게 편입시켰습니다.
- `--dry-run` 동작 시 Phase 2 워커들의 `dry_run` 상태가 정상 출력됨을 검증했습니다.

## 안전 확인
* **Derived artifacts only**: 오직 `workspace` 내부의 가공된 JSON/MD 데이터에만 읽기/쓰기를 수행했습니다.
* **No CAD mutation**: `provenance` 페이로드에 `source_mutation_allowed: false`, `cad_execution_allowed: false` 플래그를 강제 삽입했습니다.
* **No ZWCAD COM / XiCAD alias execution**: 어떠한 CAD 프로세스와의 연결이나 명령어 발송 코드가 포함되어 있지 않습니다.
* **No original DWG modification**: 원본 도면에 대한 참조 혹은 수정이 원천 차단된 구조입니다.

## 남은 TODO
- Phase 3에서 실제 Analysis 데이터 (예: 지오메트리 계산, 텍스트 OCR 결합) 등을 Megapack 내부 로직에 구현하여, 의미 있는 `metrics` 및 Payload를 채워넣는 작업이 필요합니다.
