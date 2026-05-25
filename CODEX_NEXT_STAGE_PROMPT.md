# Codex Prompt: HS-CAD Next Stage Integration

너는 HS-CAD 저장소에 next-stage overlay patch를 적용하는 코딩 에이전트다.

목표:
- zip으로 제공된 overlay를 `feature/next-stage-overlay` 브랜치에 적용한다.
- 기존 PR55 미추적 파일은 보존한다.
- safety flag는 모두 false로 유지한다.
- CAD live execution, ZWCAD COM, SendCommand, XiCAD alias execution은 구현하거나 실행하지 않는다.

작업:
1. overlay 파일을 저장소 루트에 복사하되 충돌 파일은 diff를 확인한다.
2. `python -X utf8 -m pytest -q tests/test_next_stage_overlay_contracts.py tests/test_next_stage_pipeline_smoke.py`를 실행한다.
3. `python -X utf8 -m hscad.pipelines.next_stage_pipeline --input tests/fixtures/minimal_floorplan.dxf --out outputs/next_stage_smoke`를 실행한다.
4. `python -m ruff check . --select F821,E9,F63,F7,F82`를 실행한다.
5. 가능하면 전체 `pytest -q`를 실행한다.
6. 실패하면 기존 passing tests를 깨지 않는 최소 수정만 한다.

완료 보고:
- 변경 파일 목록
- 충돌/병합한 파일
- 테스트 결과
- 생성 outputs 목록
- 남은 리스크
- 후속 PR 제안
